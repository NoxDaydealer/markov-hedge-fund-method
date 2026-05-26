from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

SYMBOLS = ["BTCUSDT", "ETHUSDT"]
DAYS = 14
INTERVAL = "1"
ROUND_TRIP_COST = 0.0012  # 12 bps: conservative taker fee + spread/slippage placeholder.
OUT_DIR = Path("research/bybit_intraday_strategy_sprint")


@dataclass(frozen=True)
class Metrics:
    bars: int
    trades: int
    long_trades: int
    short_trades: int
    wins: int
    losses: int
    win_rate: float
    gross_total_return: float
    net_total_return: float
    avg_trade_return_net: float
    median_trade_return_net: float
    profit_factor: float
    sharpe_per_bar: float
    max_drawdown: float
    exposure: float
    trades_per_day: float
    fee_to_gross_profit: float


@dataclass(frozen=True)
class ReversionParams:
    vwap_window: int
    z_window: int
    z_threshold: float
    rsi_long: float
    rsi_short: float
    volume_multiple: float
    atr_period: int
    atr_stop: float
    max_hold: int
    markov_gate: str


@dataclass(frozen=True)
class BreakoutParams:
    bb_window: int
    squeeze_quantile: float
    volume_multiple: float
    rsi_min: float
    atr_period: int
    atr_stop: float
    atr_trail: float
    max_hold: int
    markov_gate: str


def fetch_bybit_1m(symbol: str, days: int = DAYS) -> pd.DataFrame:
    url = "https://api.bybit.com/v5/market/kline"
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - days * 24 * 60 * 60 * 1000
    cursor_end = end_ms
    rows: list[list[str]] = []
    session = requests.Session()
    while cursor_end > start_ms:
        params = {
            "category": "linear",
            "symbol": symbol,
            "interval": INTERVAL,
            "end": cursor_end,
            "limit": 1000,
        }
        response = session.get(url, params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
        if payload.get("retCode") != 0:
            raise RuntimeError(f"Bybit error for {symbol}: {payload}")
        batch = payload["result"].get("list", [])
        if not batch:
            break
        rows.extend(batch)
        oldest = min(int(row[0]) for row in batch)
        next_end = oldest - 60_000
        if next_end >= cursor_end:
            break
        cursor_end = next_end
        if oldest <= start_ms:
            break
        time.sleep(0.05)
    frame = pd.DataFrame(rows, columns=["timestamp_ms", "open", "high", "low", "close", "volume", "turnover"])
    if frame.empty:
        raise RuntimeError(f"No data fetched for {symbol}")
    for column in ["open", "high", "low", "close", "volume", "turnover"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["timestamp"] = pd.to_datetime(pd.to_numeric(frame["timestamp_ms"]), unit="ms", utc=True).dt.tz_convert(None)
    frame = frame.drop_duplicates("timestamp").sort_values("timestamp").set_index("timestamp")
    frame = frame.loc[frame.index >= pd.Timestamp.fromtimestamp(start_ms / 1000, tz="UTC").tz_convert(None)]
    frame = frame[["open", "high", "low", "close", "volume", "turnover"]].dropna().copy()
    return frame


def add_features(frame: pd.DataFrame) -> pd.DataFrame:
    f = frame.copy()
    typical = (f["high"] + f["low"] + f["close"]) / 3.0
    f["tpv"] = typical * f["volume"]
    f["rsi14"] = rsi(f["close"], 14)
    f["atr14"] = atr(f, 14)
    f["ret1"] = f["close"].pct_change()
    f["markov_score"] = intraday_markov_score(f["close"])
    return f


def rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50.0)


def atr(frame: pd.DataFrame, period: int) -> pd.Series:
    prev_close = frame["close"].shift(1)
    tr = pd.concat([
        frame["high"] - frame["low"],
        (frame["high"] - prev_close).abs(),
        (frame["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def intraday_markov_score(close: pd.Series) -> pd.Series:
    # 15m close labels, fit transition probabilities walk-forward, then forward-fill to 1m.
    close15 = close.resample("15min").last().dropna()
    rolling_ret = close15.pct_change(16)  # approx 4h context.
    labels = pd.Series(1, index=close15.index, dtype=float)
    labels[rolling_ret > 0.003] = 2
    labels[rolling_ret < -0.003] = 0
    labels = labels.where(rolling_ret.notna())
    scores = pd.Series(0.0, index=close15.index)
    arr = labels.to_numpy()
    min_train = 64
    for i in range(len(labels)):
        if i < min_train or math.isnan(arr[i]):
            continue
        hist = arr[: i + 1]
        hist = hist[~np.isnan(hist)].astype(int)
        if len(hist) < min_train:
            continue
        counts = np.ones((3, 3), dtype=float) * 0.5
        for a, b in zip(hist[:-1], hist[1:]):
            counts[a, b] += 1
        matrix = counts / counts.sum(axis=1, keepdims=True)
        cur = int(hist[-1])
        scores.iloc[i] = float(matrix[cur, 2] - matrix[cur, 0])
    return scores.reindex(close.index, method="ffill").fillna(0.0)


def rolling_vwap(frame: pd.DataFrame, window: int) -> pd.Series:
    typical = (frame["high"] + frame["low"] + frame["close"]) / 3.0
    return (typical * frame["volume"]).rolling(window, min_periods=window).sum() / frame["volume"].rolling(window, min_periods=window).sum()


def reversion_positions(frame: pd.DataFrame, p: ReversionParams) -> pd.Series:
    vwap = rolling_vwap(frame, p.vwap_window)
    dist = frame["close"] / vwap - 1.0
    z = (dist - dist.rolling(p.z_window, min_periods=p.z_window).mean()) / dist.rolling(p.z_window, min_periods=p.z_window).std(ddof=0)
    vol_med = frame["volume"].rolling(60, min_periods=60).median()
    vol_spike = frame["volume"] > p.volume_multiple * vol_med
    prior_high = frame["high"].shift(1)
    prior_low = frame["low"].shift(1)
    long_setup = (z <= -p.z_threshold) & (frame["rsi14"] <= p.rsi_long) & vol_spike & (frame["close"] > prior_high)
    short_setup = (z >= p.z_threshold) & (frame["rsi14"] >= p.rsi_short) & vol_spike & (frame["close"] < prior_low)
    raw = pd.Series(0, index=frame.index, dtype=int)
    raw.loc[long_setup] = 1
    raw.loc[short_setup] = -1
    if p.markov_gate == "neutral_only":
        raw.loc[frame["markov_score"].abs() > 0.12] = 0
    elif p.markov_gate == "contrarian_ok":
        raw.loc[(raw == 1) & (frame["markov_score"] < -0.20)] = 0
        raw.loc[(raw == -1) & (frame["markov_score"] > 0.20)] = 0
    elif p.markov_gate != "off":
        raise ValueError(p.markov_gate)
    return raw.shift(1, fill_value=0).astype(int)


def breakout_positions(frame: pd.DataFrame, p: BreakoutParams) -> pd.Series:
    mid = frame["close"].rolling(p.bb_window, min_periods=p.bb_window).mean()
    std = frame["close"].rolling(p.bb_window, min_periods=p.bb_window).std(ddof=0)
    upper = mid + 2 * std
    lower = mid - 2 * std
    width = (upper - lower) / mid
    squeeze_level = width.rolling(24 * 60, min_periods=240).quantile(p.squeeze_quantile)
    in_squeeze = width.shift(1) <= squeeze_level.shift(1)
    vwap = rolling_vwap(frame, 240)
    vol_med = frame["volume"].rolling(60, min_periods=60).median()
    vol_spike = frame["volume"] > p.volume_multiple * vol_med
    long_setup = in_squeeze & (frame["close"] > upper) & (frame["close"] > vwap) & vol_spike & (frame["rsi14"] >= p.rsi_min)
    short_setup = in_squeeze & (frame["close"] < lower) & (frame["close"] < vwap) & vol_spike & (frame["rsi14"] <= 100 - p.rsi_min)
    raw = pd.Series(0, index=frame.index, dtype=int)
    raw.loc[long_setup] = 1
    raw.loc[short_setup] = -1
    if p.markov_gate == "trend_only":
        raw.loc[(raw == 1) & (frame["markov_score"] <= 0.05)] = 0
        raw.loc[(raw == -1) & (frame["markov_score"] >= -0.05)] = 0
    elif p.markov_gate != "off":
        raise ValueError(p.markov_gate)
    return raw.shift(1, fill_value=0).astype(int)


def simulate_trades(frame: pd.DataFrame, positions: pd.Series, *, max_hold: int, atr_stop: float, target: str, atr_trail: float | None = None) -> tuple[pd.Series, pd.DataFrame, pd.Series]:
    net_returns = pd.Series(0.0, index=frame.index)
    gross_returns = pd.Series(0.0, index=frame.index)
    records: list[dict[str, Any]] = []
    target_vwap = rolling_vwap(frame, 240) if target == "vwap" else None
    in_trade_until = -1
    idx = list(frame.index)
    for i, ts in enumerate(idx[:-1]):
        if i <= in_trade_until:
            continue
        side = int(positions.iloc[i])
        if side == 0 or not np.isfinite(frame["atr14"].iloc[i]):
            continue
        entry_i = i
        entry_price = float(frame["open"].iloc[entry_i])
        atr_value = float(frame["atr14"].iloc[entry_i])
        if atr_value <= 0:
            continue
        stop_price = entry_price - side * atr_stop * atr_value
        best_price = entry_price
        exit_i = min(entry_i + max_hold, len(frame) - 1)
        exit_price = float(frame["close"].iloc[exit_i])
        exit_reason = "time"
        for j in range(entry_i + 1, min(entry_i + max_hold, len(frame) - 1) + 1):
            high = float(frame["high"].iloc[j])
            low = float(frame["low"].iloc[j])
            close = float(frame["close"].iloc[j])
            if atr_trail is not None:
                if side == 1:
                    best_price = max(best_price, high)
                    stop_price = max(stop_price, best_price - atr_trail * atr_value)
                else:
                    best_price = min(best_price, low)
                    stop_price = min(stop_price, best_price + atr_trail * atr_value)
            if side == 1 and low <= stop_price:
                exit_i, exit_price, exit_reason = j, stop_price, "stop"
                break
            if side == -1 and high >= stop_price:
                exit_i, exit_price, exit_reason = j, stop_price, "stop"
                break
            if target == "vwap":
                vwap_now = target_vwap.iloc[j] if target_vwap is not None else np.nan
                if np.isfinite(vwap_now):
                    if side == 1 and high >= vwap_now:
                        exit_i, exit_price, exit_reason = j, float(vwap_now), "vwap"
                        break
                    if side == -1 and low <= vwap_now:
                        exit_i, exit_price, exit_reason = j, float(vwap_now), "vwap"
                        break
            elif target == "trail" and j > entry_i + 1:
                # trailing stop or time stop only; let breakout run.
                pass
            exit_i, exit_price = j, close
        gross = side * (exit_price / entry_price - 1.0)
        net = gross - ROUND_TRIP_COST
        gross_returns.iloc[exit_i] += gross
        net_returns.iloc[exit_i] += net
        records.append({
            "entry_time": str(ts),
            "exit_time": str(idx[exit_i]),
            "side": side,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "gross_return": gross,
            "net_return": net,
            "hold_bars": exit_i - entry_i,
            "exit_reason": exit_reason,
        })
        in_trade_until = exit_i
    return net_returns, pd.DataFrame.from_records(records), gross_returns


def compute_metrics(frame: pd.DataFrame, returns: pd.Series, positions: pd.Series, trades: pd.DataFrame, gross_returns: pd.Series) -> Metrics:
    trade_returns = trades["net_return"].astype(float) if not trades.empty else pd.Series(dtype=float)
    gross_trade_returns = trades["gross_return"].astype(float) if not trades.empty else pd.Series(dtype=float)
    equity = (1.0 + returns).cumprod()
    drawdown = equity / equity.cummax() - 1.0
    wins = int((trade_returns > 0).sum())
    losses = int((trade_returns < 0).sum())
    gross_profit = float(gross_trade_returns[gross_trade_returns > 0].sum()) if len(gross_trade_returns) else 0.0
    gross_loss = float(-gross_trade_returns[gross_trade_returns < 0].sum()) if len(gross_trade_returns) else 0.0
    days = max((frame.index.max() - frame.index.min()).total_seconds() / 86400.0, 1e-9)
    std = float(returns.std(ddof=0))
    return Metrics(
        bars=int(len(frame)),
        trades=int(len(trades)),
        long_trades=int((trades["side"] == 1).sum()) if not trades.empty else 0,
        short_trades=int((trades["side"] == -1).sum()) if not trades.empty else 0,
        wins=wins,
        losses=losses,
        win_rate=float(wins / len(trades)) if len(trades) else 0.0,
        gross_total_return=float((1.0 + gross_returns).prod() - 1.0),
        net_total_return=float(equity.iloc[-1] - 1.0) if len(equity) else 0.0,
        avg_trade_return_net=float(trade_returns.mean()) if len(trade_returns) else 0.0,
        median_trade_return_net=float(trade_returns.median()) if len(trade_returns) else 0.0,
        profit_factor=float(gross_profit / gross_loss) if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0),
        sharpe_per_bar=float((returns.mean() / std) * np.sqrt(365 * 24 * 60)) if std > 0 else 0.0,
        max_drawdown=float(drawdown.min()) if len(drawdown) else 0.0,
        exposure=float((positions != 0).mean()) if len(positions) else 0.0,
        trades_per_day=float(len(trades) / days),
        fee_to_gross_profit=float((len(trades) * ROUND_TRIP_COST) / gross_profit) if gross_profit > 0 else float("inf"),
    )


def split_train_test(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    cut = int(len(frame) * 0.70)
    return frame.iloc[:cut].copy(), frame.iloc[cut:].copy()


def evaluate_reversion(frame: pd.DataFrame, p: ReversionParams) -> tuple[pd.Series, pd.DataFrame, pd.Series, Metrics, Metrics, Metrics]:
    pos = reversion_positions(frame, p)
    net, trades, gross = simulate_trades(frame, pos, max_hold=p.max_hold, atr_stop=p.atr_stop, target="vwap")
    train, test = split_train_test(frame)
    train_m = compute_metrics(train, net.loc[train.index], pos.loc[train.index], trades[pd.to_datetime(trades.get("entry_time", pd.Series(dtype=str))).isin(train.index)] if not trades.empty else trades, gross.loc[train.index])
    test_m = compute_metrics(test, net.loc[test.index], pos.loc[test.index], trades[pd.to_datetime(trades.get("entry_time", pd.Series(dtype=str))).isin(test.index)] if not trades.empty else trades, gross.loc[test.index])
    all_m = compute_metrics(frame, net, pos, trades, gross)
    return pos, trades, net, train_m, test_m, all_m


def evaluate_breakout(frame: pd.DataFrame, p: BreakoutParams) -> tuple[pd.Series, pd.DataFrame, pd.Series, Metrics, Metrics, Metrics]:
    pos = breakout_positions(frame, p)
    net, trades, gross = simulate_trades(frame, pos, max_hold=p.max_hold, atr_stop=p.atr_stop, target="trail", atr_trail=p.atr_trail)
    train, test = split_train_test(frame)
    train_m = compute_metrics(train, net.loc[train.index], pos.loc[train.index], trades[pd.to_datetime(trades.get("entry_time", pd.Series(dtype=str))).isin(train.index)] if not trades.empty else trades, gross.loc[train.index])
    test_m = compute_metrics(test, net.loc[test.index], pos.loc[test.index], trades[pd.to_datetime(trades.get("entry_time", pd.Series(dtype=str))).isin(test.index)] if not trades.empty else trades, gross.loc[test.index])
    all_m = compute_metrics(frame, net, pos, trades, gross)
    return pos, trades, net, train_m, test_m, all_m


def reversion_grid() -> list[ReversionParams]:
    return [ReversionParams(*values) for values in product(
        [120, 240],
        [240],
        [1.0, 1.5, 2.0],
        [30, 35],
        [65, 70],
        [1.2, 1.5],
        [14],
        [0.8, 1.2],
        [10, 20],
        ["off", "neutral_only", "contrarian_ok"],
    )]


def breakout_grid() -> list[BreakoutParams]:
    return [BreakoutParams(*values) for values in product(
        [20, 40],
        [0.10, 0.20],
        [1.2, 1.5],
        [50, 55],
        [14],
        [0.8, 1.2],
        [1.0, 1.5],
        [20, 40],
        ["off", "trend_only"],
    )]


def select_best(rows: list[dict[str, Any]], min_test_trades: int = 25) -> dict[str, Any]:
    frame = pd.DataFrame(rows)
    eligible = frame[(frame["train_trades"] >= 50) & (frame["test_trades"] >= min_test_trades)]
    if eligible.empty:
        eligible = frame[(frame["train_trades"] >= 20) & (frame["test_trades"] >= 5)]
    if eligible.empty:
        eligible = frame
    eligible = eligible.copy()
    # Choose on train first, with enough activity, then inspect test in summary.
    eligible["score"] = eligible["train_avg_trade_return_net"] * 1000 + eligible["train_profit_factor"].replace(np.inf, 10) * 0.01 - eligible["train_max_drawdown"].abs() * 0.1
    return eligible.sort_values(["score", "train_trades"], ascending=False).iloc[0].to_dict()


def run() -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data_dir = OUT_DIR / "data"
    data_dir.mkdir(exist_ok=True)
    summary: dict[str, Any] = {
        "settings": {
            "symbols": SYMBOLS,
            "days": DAYS,
            "interval": "1m",
            "round_trip_cost": ROUND_TRIP_COST,
            "train_fraction": 0.70,
            "source": "Bybit public REST /v5/market/kline, category=linear, no API key",
        },
        "symbols": {},
    }
    all_rows: list[dict[str, Any]] = []
    for symbol in SYMBOLS:
        frame = add_features(fetch_bybit_1m(symbol))
        frame.to_csv(data_dir / f"{symbol}_1m.csv")
        train, test = split_train_test(frame)
        rows: list[dict[str, Any]] = []
        best_payloads: dict[tuple[str, str], tuple[pd.Series, pd.DataFrame, pd.Series]] = {}
        for strategy, grid, evaluator in [
            ("vwap_volume_rsi_reversion", reversion_grid(), evaluate_reversion),
            ("bb_vwap_momentum_breakout", breakout_grid(), evaluate_breakout),
        ]:
            strat_rows = []
            for params in grid:
                pos, trades, net, train_m, test_m, all_m = evaluator(frame, params)  # type: ignore[arg-type]
                row = {
                    "symbol": symbol,
                    "strategy": strategy,
                    **asdict(params),
                    **{f"train_{k}": v for k, v in asdict(train_m).items()},
                    **{f"test_{k}": v for k, v in asdict(test_m).items()},
                    **{f"all_{k}": v for k, v in asdict(all_m).items()},
                }
                rows.append(row)
                strat_rows.append(row)
            best = select_best(strat_rows)
            best_key = (strategy, json.dumps({k: best[k] for k in asdict(grid[0]).keys()}, sort_keys=True))
            # Recompute selected payload once for CSV outputs.
            if strategy == "vwap_volume_rsi_reversion":
                p = ReversionParams(**{k: best[k] for k in ReversionParams.__dataclass_fields__.keys()})
                best_payloads[best_key] = evaluate_reversion(frame, p)[:3]
            else:
                p = BreakoutParams(**{k: best[k] for k in BreakoutParams.__dataclass_fields__.keys()})
                best_payloads[best_key] = evaluate_breakout(frame, p)[:3]
            pd.DataFrame(strat_rows).to_csv(OUT_DIR / f"{symbol}_{strategy}_sweep.csv", index=False)
        result_frame = pd.DataFrame(rows)
        result_frame.to_csv(OUT_DIR / f"{symbol}_all_sweep.csv", index=False)
        all_rows.extend(rows)
        selected = {}
        for strategy in ["vwap_volume_rsi_reversion", "bb_vwap_momentum_breakout"]:
            strat_rows = [row for row in rows if row["strategy"] == strategy]
            best = select_best(strat_rows)
            param_fields = ReversionParams.__dataclass_fields__.keys() if strategy.startswith("vwap") else BreakoutParams.__dataclass_fields__.keys()
            selected[strategy] = {
                "selected_params_train_first": {k: best[k] for k in param_fields},
                "train": {k.replace("train_", ""): best[k] for k in best if k.startswith("train_")},
                "test": {k.replace("test_", ""): best[k] for k in best if k.startswith("test_")},
                "all": {k.replace("all_", ""): best[k] for k in best if k.startswith("all_")},
                "sweep_csv": str(OUT_DIR / f"{symbol}_{strategy}_sweep.csv"),
            }
        summary["symbols"][symbol] = {
            "rows": int(len(frame)),
            "start": str(frame.index.min()),
            "end": str(frame.index.max()),
            "train_start": str(train.index.min()),
            "train_end": str(train.index.max()),
            "test_start": str(test.index.min()),
            "test_end": str(test.index.max()),
            "data_csv": str(data_dir / f"{symbol}_1m.csv"),
            "selected": selected,
        }
    pd.DataFrame(all_rows).to_csv(OUT_DIR / "all_symbols_all_sweeps.csv", index=False)
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=True), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, allow_nan=True))
