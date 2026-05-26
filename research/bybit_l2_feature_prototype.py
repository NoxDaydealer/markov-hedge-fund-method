from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import requests

DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT"]
DEFAULT_TOP_NS = [1, 5, 10, 25, 50]
BYBIT_BASE_URL = "https://api.bybit.com"
OUT_DIR = Path("research/bybit_l2_feature_prototype")


@dataclass(frozen=True)
class L2Config:
    symbols: list[str]
    category: str
    samples: int
    interval_seconds: float
    orderbook_limit: int
    top_ns: list[int]
    out_dir: Path


class BybitPublicClient:
    def __init__(self, *, base_url: str = BYBIT_BASE_URL, timeout: float = 20.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        response = self.session.get(f"{self.base_url}{path}", params=params, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        if payload.get("retCode") != 0:
            raise RuntimeError(f"Bybit public API error: {payload}")
        return payload["result"]

    def orderbook(self, *, category: str, symbol: str, limit: int) -> dict[str, Any]:
        return self._get("/v5/market/orderbook", {"category": category, "symbol": symbol, "limit": limit})

    def recent_trades(self, *, category: str, symbol: str, limit: int = 100) -> list[dict[str, Any]]:
        result = self._get("/v5/market/recent-trade", {"category": category, "symbol": symbol, "limit": limit})
        return list(result.get("list", []))


def _parse_levels(levels: list[list[str]]) -> list[tuple[float, float]]:
    parsed: list[tuple[float, float]] = []
    for row in levels:
        if len(row) < 2:
            continue
        price = float(row[0])
        qty = float(row[1])
        if math.isfinite(price) and math.isfinite(qty) and price > 0 and qty >= 0:
            parsed.append((price, qty))
    return parsed


def _sum_qty(levels: list[tuple[float, float]], n: int) -> float:
    return float(sum(qty for _, qty in levels[:n]))


def _sum_notional(levels: list[tuple[float, float]], n: int) -> float:
    return float(sum(price * qty for price, qty in levels[:n]))


def _weighted_average_price(levels: list[tuple[float, float]], n: int) -> float:
    qty = _sum_qty(levels, n)
    if qty <= 0:
        return float("nan")
    return _sum_notional(levels, n) / qty


def _safe_ratio(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def compute_orderbook_features(
    orderbook: dict[str, Any],
    *,
    symbol: str,
    top_ns: list[int],
    previous_depths: dict[int, tuple[float, float]] | None = None,
) -> tuple[dict[str, Any], dict[int, tuple[float, float]]]:
    bids = _parse_levels(orderbook.get("b", []))
    asks = _parse_levels(orderbook.get("a", []))
    if not bids or not asks:
        raise ValueError(f"orderbook for {symbol} has no usable bids/asks")

    best_bid, best_bid_qty = bids[0]
    best_ask, best_ask_qty = asks[0]
    mid = (best_bid + best_ask) / 2.0
    spread = best_ask - best_bid
    top_microprice = (best_ask * best_bid_qty + best_bid * best_ask_qty) / (best_bid_qty + best_ask_qty)

    ts_ms = int(orderbook.get("ts") or orderbook.get("u") or 0)
    features: dict[str, Any] = {
        "timestamp": pd.to_datetime(ts_ms, unit="ms", utc=True).isoformat() if ts_ms else pd.Timestamp.utcnow().isoformat(),
        "timestamp_ms": ts_ms,
        "symbol": symbol,
        "update_id": int(orderbook.get("u", 0) or 0),
        "seq": int(orderbook.get("seq", 0) or 0),
        "best_bid": best_bid,
        "best_ask": best_ask,
        "best_bid_qty": best_bid_qty,
        "best_ask_qty": best_ask_qty,
        "mid": mid,
        "spread": spread,
        "spread_bps": _safe_ratio(spread, mid) * 10_000,
        "microprice_top1": top_microprice,
        "microprice_top1_edge_bps": _safe_ratio(top_microprice - mid, mid) * 10_000,
    }

    current_depths: dict[int, tuple[float, float]] = {}
    for n in top_ns:
        bid_qty = _sum_qty(bids, n)
        ask_qty = _sum_qty(asks, n)
        bid_notional = _sum_notional(bids, n)
        ask_notional = _sum_notional(asks, n)
        total_qty = bid_qty + ask_qty
        total_notional = bid_notional + ask_notional
        wap_bid = _weighted_average_price(bids, n)
        wap_ask = _weighted_average_price(asks, n)
        imbalance_qty = _safe_ratio(bid_qty - ask_qty, total_qty)
        imbalance_notional = _safe_ratio(bid_notional - ask_notional, total_notional)
        # A top-N microprice-like pressure price. More bid size pulls expected execution price toward asks;
        # more ask size pulls it toward bids. This is a feature, not a fill assumption.
        pressure_price = _safe_ratio(wap_ask * bid_qty + wap_bid * ask_qty, total_qty)
        features.update(
            {
                f"bid_qty_top{n}": bid_qty,
                f"ask_qty_top{n}": ask_qty,
                f"bid_notional_top{n}": bid_notional,
                f"ask_notional_top{n}": ask_notional,
                f"imbalance_qty_top{n}": imbalance_qty,
                f"imbalance_notional_top{n}": imbalance_notional,
                f"wap_bid_top{n}": wap_bid,
                f"wap_ask_top{n}": wap_ask,
                f"pressure_price_top{n}": pressure_price,
                f"pressure_edge_bps_top{n}": _safe_ratio(pressure_price - mid, mid) * 10_000,
            }
        )
        if previous_depths and n in previous_depths:
            prev_bid_qty, prev_ask_qty = previous_depths[n]
            bid_delta = bid_qty - prev_bid_qty
            ask_delta = ask_qty - prev_ask_qty
            features[f"bid_qty_delta_top{n}"] = bid_delta
            features[f"ask_qty_delta_top{n}"] = ask_delta
            features[f"orderbook_delta_imbalance_top{n}"] = _safe_ratio(bid_delta - ask_delta, abs(bid_delta) + abs(ask_delta))
        else:
            features[f"bid_qty_delta_top{n}"] = 0.0
            features[f"ask_qty_delta_top{n}"] = 0.0
            features[f"orderbook_delta_imbalance_top{n}"] = 0.0
        current_depths[n] = (bid_qty, ask_qty)

    return features, current_depths


def compute_aggressive_trade_flow(
    trades: list[dict[str, Any]],
    *,
    seen_exec_ids: set[str],
    previous_trade_ts: int | None,
) -> tuple[dict[str, Any], set[str], int | None]:
    new_trades: list[dict[str, Any]] = []
    max_ts = previous_trade_ts
    updated_seen = set(seen_exec_ids)
    for trade in trades:
        exec_id = str(trade.get("execId") or trade.get("i") or "")
        ts = int(trade.get("time") or trade.get("T") or 0)
        if exec_id and exec_id in updated_seen:
            continue
        if previous_trade_ts is not None and ts <= previous_trade_ts and not exec_id:
            continue
        if exec_id:
            updated_seen.add(exec_id)
        new_trades.append(trade)
        if ts:
            max_ts = ts if max_ts is None else max(max_ts, ts)

    buy_qty = sell_qty = buy_notional = sell_notional = 0.0
    buy_count = sell_count = 0
    for trade in new_trades:
        side = str(trade.get("side", "")).lower()
        price = float(trade.get("price") or trade.get("p") or 0.0)
        qty = float(trade.get("size") or trade.get("v") or 0.0)
        notional = price * qty
        # Bybit public recent-trade side is treated as aggressor/taker side for this prototype.
        # Keep this as a feature proxy only; validate against websocket semantics before trading.
        if side == "buy":
            buy_qty += qty
            buy_notional += notional
            buy_count += 1
        elif side == "sell":
            sell_qty += qty
            sell_notional += notional
            sell_count += 1

    total_qty = buy_qty + sell_qty
    total_notional = buy_notional + sell_notional
    total_count = buy_count + sell_count
    features = {
        "new_trade_count": total_count,
        "aggressive_buy_count": buy_count,
        "aggressive_sell_count": sell_count,
        "aggressive_buy_qty": buy_qty,
        "aggressive_sell_qty": sell_qty,
        "aggressive_buy_notional": buy_notional,
        "aggressive_sell_notional": sell_notional,
        "aggressive_flow_qty_imbalance": _safe_ratio(buy_qty - sell_qty, total_qty),
        "aggressive_flow_notional_imbalance": _safe_ratio(buy_notional - sell_notional, total_notional),
    }
    return features, updated_seen, max_ts


def collect_feature_dataset(config: L2Config, client: BybitPublicClient) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    previous_depths_by_symbol: dict[str, dict[int, tuple[float, float]]] = {}
    seen_exec_ids_by_symbol: dict[str, set[str]] = {symbol: set() for symbol in config.symbols}
    previous_trade_ts_by_symbol: dict[str, int | None] = {symbol: None for symbol in config.symbols}

    for sample_index in range(config.samples):
        sample_started = time.time()
        for symbol in config.symbols:
            orderbook = client.orderbook(category=config.category, symbol=symbol, limit=config.orderbook_limit)
            trades = client.recent_trades(category=config.category, symbol=symbol, limit=100)
            book_features, current_depths = compute_orderbook_features(
                orderbook,
                symbol=symbol,
                top_ns=config.top_ns,
                previous_depths=previous_depths_by_symbol.get(symbol),
            )
            trade_features, seen_ids, max_trade_ts = compute_aggressive_trade_flow(
                trades,
                seen_exec_ids=seen_exec_ids_by_symbol[symbol],
                previous_trade_ts=previous_trade_ts_by_symbol[symbol],
            )
            previous_depths_by_symbol[symbol] = current_depths
            seen_exec_ids_by_symbol[symbol] = seen_ids
            previous_trade_ts_by_symbol[symbol] = max_trade_ts
            rows.append({"sample_index": sample_index, **book_features, **trade_features})
        elapsed = time.time() - sample_started
        if sample_index < config.samples - 1:
            time.sleep(max(0.0, config.interval_seconds - elapsed))
    return pd.DataFrame(rows)


def _series_stats(series: pd.Series) -> dict[str, float]:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return {"mean": 0.0, "median": 0.0, "min": 0.0, "max": 0.0, "stdev": 0.0}
    return {
        "mean": float(clean.mean()),
        "median": float(clean.median()),
        "min": float(clean.min()),
        "max": float(clean.max()),
        "stdev": float(clean.std(ddof=0)),
    }


def make_diagnostics(frame: pd.DataFrame, *, config: L2Config) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {
        "scope": "Bybit public REST L2 orderbook/trade-flow feature prototype; research only, no orders.",
        "category": config.category,
        "symbols": config.symbols,
        "samples_requested": config.samples,
        "samples_collected_rows": int(len(frame)),
        "top_ns": config.top_ns,
        "interval_seconds": config.interval_seconds,
        "orderbook_limit": config.orderbook_limit,
        "caveats": [
            "REST snapshots are not a lossless historical L2 stream; use websocket deltas with sequence-gap checks before live-like paper reporting.",
            "Microprice, top-N pressure, and imbalance columns are predictive features only, not executable fill prices.",
            "Do not assume fills at mid-price; conservative simulation should cross spread for taker fills or model maker queue priority, latency, cancels, and partial fills.",
            "Bybit recent-trade side is treated as aggressor/taker-side proxy here; confirm endpoint semantics against websocket trade docs before using as alpha.",
            "Orderbook delta imbalance compares sampled depth snapshots; it misses within-interval add/cancel/trade events and is sensitive to polling cadence.",
        ],
        "by_symbol": {},
        "overall_verdict": "Dataset generated for feature diagnostics only; not a strategy and not ready for live orders.",
    }
    for symbol, group in frame.groupby("symbol"):
        topn_summary = {}
        for n in config.top_ns:
            topn_summary[str(n)] = {
                "imbalance_qty": _series_stats(group[f"imbalance_qty_top{n}"]),
                "imbalance_notional": _series_stats(group[f"imbalance_notional_top{n}"]),
                "orderbook_delta_imbalance": _series_stats(group[f"orderbook_delta_imbalance_top{n}"]),
                "pressure_edge_bps": _series_stats(group[f"pressure_edge_bps_top{n}"]),
            }
        diagnostics["by_symbol"][symbol] = {
            "rows": int(len(group)),
            "time_start": str(group["timestamp"].iloc[0]) if len(group) else None,
            "time_end": str(group["timestamp"].iloc[-1]) if len(group) else None,
            "spread_bps": _series_stats(group["spread_bps"]),
            "microprice_top1_edge_bps": _series_stats(group["microprice_top1_edge_bps"]),
            "aggressive_flow_qty_imbalance": _series_stats(group["aggressive_flow_qty_imbalance"]),
            "aggressive_flow_notional_imbalance": _series_stats(group["aggressive_flow_notional_imbalance"]),
            "new_trade_count": _series_stats(group["new_trade_count"]),
            "top_n": topn_summary,
        }
    return diagnostics


def write_report(diagnostics: dict[str, Any], dataset_path: Path, summary_path: Path, report_path: Path) -> None:
    lines = [
        "# Bybit L2 Orderbook Imbalance Feature Prototype",
        "",
        "## Scope",
        "",
        "Research-only feature prototype for Paper Trading. No broker keys, fills, or live orders were used.",
        "The generated CSV is a feature dataset from Bybit public REST orderbook snapshots plus recent trades.",
        "It is not a backtest and not a strategy recommendation.",
        "",
        "Artifacts:",
        f"- Feature dataset: `{dataset_path}`",
        f"- Machine diagnostics: `{summary_path}`",
        f"- Runner: `research/bybit_l2_feature_prototype.py`",
        "",
        "## Features",
        "",
        "Per symbol and snapshot the dataset includes:",
        "- Best bid/ask, mid, spread, spread in bps.",
        "- Top-1 microprice and edge vs mid in bps.",
        "- Top-N bid/ask quantity and notional depth for configured N values.",
        "- Top-N quantity and notional imbalance: `(bid - ask) / (bid + ask)`.",
        "- Top-N pressure price/edge, a microprice-like book-pressure feature.",
        "- Top-N orderbook delta imbalance from consecutive sampled snapshots.",
        "- Recent public-trade buy/sell count, size, notional, and aggressive-flow imbalance since prior sample.",
        "",
        "## Diagnostics",
        "",
    ]
    for symbol, info in diagnostics["by_symbol"].items():
        lines.extend(
            [
                f"### {symbol}",
                "",
                f"Rows: {info['rows']} from {info['time_start']} to {info['time_end']}.",
                f"Spread bps mean/median/max: {info['spread_bps']['mean']:.4f} / {info['spread_bps']['median']:.4f} / {info['spread_bps']['max']:.4f}.",
                f"Top-1 microprice edge bps mean/median: {info['microprice_top1_edge_bps']['mean']:.4f} / {info['microprice_top1_edge_bps']['median']:.4f}.",
                f"Aggressive notional-flow imbalance mean/median: {info['aggressive_flow_notional_imbalance']['mean']:.4f} / {info['aggressive_flow_notional_imbalance']['median']:.4f}.",
                "",
                "Top-N imbalance means:",
            ]
        )
        for n, top_info in info["top_n"].items():
            lines.append(
                f"- N={n}: qty imbalance mean {top_info['imbalance_qty']['mean']:.4f}, "
                f"notional imbalance mean {top_info['imbalance_notional']['mean']:.4f}, "
                f"delta imbalance mean {top_info['orderbook_delta_imbalance']['mean']:.4f}, "
                f"pressure edge mean {top_info['pressure_edge_bps']['mean']:.4f} bps."
            )
        lines.append("")
    lines.extend(
        [
            "## Conservative queue/fill caveats",
            "",
            *[f"- {caveat}" for caveat in diagnostics["caveats"]],
            "",
            "## Bottom line",
            "",
            diagnostics["overall_verdict"],
            "Next step: feed this feature schema from a websocket collector that stores orderbook.50 deltas, best bid/ask, and public trades with strict sequence validation; only then evaluate signals with spread/queue/latency-aware paper fills.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect Bybit L2 feature prototype dataset from public REST snapshots.")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    parser.add_argument("--category", default="linear")
    parser.add_argument("--samples", type=int, default=60)
    parser.add_argument("--interval-seconds", type=float, default=1.0)
    parser.add_argument("--orderbook-limit", type=int, default=50)
    parser.add_argument("--top-n", nargs="+", type=int, default=DEFAULT_TOP_NS)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    top_ns = sorted(set(args.top_n))
    if not top_ns or min(top_ns) <= 0:
        raise SystemExit("--top-n values must be positive integers")
    if max(top_ns) > args.orderbook_limit:
        raise SystemExit("max --top-n cannot exceed --orderbook-limit")
    if args.samples <= 0:
        raise SystemExit("--samples must be positive")

    config = L2Config(
        symbols=list(args.symbols),
        category=args.category,
        samples=args.samples,
        interval_seconds=args.interval_seconds,
        orderbook_limit=args.orderbook_limit,
        top_ns=top_ns,
        out_dir=args.out_dir,
    )
    config.out_dir.mkdir(parents=True, exist_ok=True)
    client = BybitPublicClient()
    frame = collect_feature_dataset(config, client)
    dataset_path = config.out_dir / "features.csv"
    summary_path = config.out_dir / "summary.json"
    report_path = config.out_dir / "README.md"
    frame.to_csv(dataset_path, index=False)
    diagnostics = make_diagnostics(frame, config=config)
    summary_path.write_text(json.dumps(diagnostics, indent=2, sort_keys=True), encoding="utf-8")
    write_report(diagnostics, dataset_path, summary_path, report_path)
    print(json.dumps({"rows": int(len(frame)), "dataset": str(dataset_path), "summary": str(summary_path), "report": str(report_path)}, indent=2))


if __name__ == "__main__":
    main()
