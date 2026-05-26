from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd


ASSETS = ["QQQ", "^IXIC", "NQ=F"]
PERIOD = "5y"
INTERVAL = "1d"
PERIODS_PER_YEAR = 252
TRAIN_FRACTION = 0.60
ROUND_TRIP_COST = 0.0010  # 10 bps per completed one-bar trade, conservative for ETF/index/futures proxy research.
MIN_TEST_TRADES = 5


@dataclass(frozen=True)
class Params:
    lookback: int
    fib_level: float
    require_candle_direction: bool
    allow_shorts: bool
    markov_gate: str  # off, long_nonnegative, directional
    markov_window: int
    markov_threshold: float
    min_train: int


@dataclass
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
    annualized_return: float
    sharpe: float
    max_drawdown: float
    avg_trade_return_net: float
    exposure: float


def fetch_ohlcv(symbol: str) -> pd.DataFrame:
    import yfinance as yf

    frame = yf.download(symbol, period=PERIOD, interval=INTERVAL, auto_adjust=False, progress=False, threads=False)
    if frame is None or frame.empty:
        raise RuntimeError(f"No yfinance data for {symbol}")
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = [str(c[0]).lower() for c in frame.columns]
    else:
        frame.columns = [str(c).lower() for c in frame.columns]
    rename = {"adj close": "adj_close"}
    frame = frame.rename(columns=rename)
    frame = frame[["open", "high", "low", "close", "volume"]].dropna().copy()
    frame.index = pd.DatetimeIndex(frame.index).tz_localize(None)
    return frame


def markov_signal(close: pd.Series, *, window: int, threshold: float, min_train: int) -> pd.Series:
    """Walk-forward Markov signal fit only on historical labels before each row."""
    rolling_return = close.pct_change(window)
    labels = pd.Series(1, index=close.index, dtype=int)
    labels[rolling_return > threshold] = 2
    labels[rolling_return < -threshold] = 0
    labels = labels.where(rolling_return.notna())

    out = pd.Series(0.0, index=close.index)
    label_arr = labels.to_numpy()
    for i in range(len(close) - 1):
        if i < min_train or math.isnan(label_arr[i]):
            continue
        hist = label_arr[: i + 1]
        hist = hist[~np.isnan(hist)].astype(int)
        if len(hist) < min_train:
            continue
        counts = np.ones((3, 3), dtype=float) * 0.25  # mild smoothing for sparse states
        for a, b in zip(hist[:-1], hist[1:]):
            counts[a, b] += 1.0
        matrix = counts / counts.sum(axis=1, keepdims=True)
        current = int(hist[-1])
        out.iloc[i] = float(matrix[current, 2] - matrix[current, 0])
    return out


def combo_positions(frame: pd.DataFrame, p: Params, markov_cache: dict[tuple[int, float, int], pd.Series] | None = None) -> pd.Series:
    prior_high = frame["high"].shift(1).rolling(p.lookback, min_periods=p.lookback).max()
    prior_low = frame["low"].shift(1).rolling(p.lookback, min_periods=p.lookback).min()
    prior_range = prior_high - prior_low
    fib_line = prior_low + prior_range * p.fib_level

    swept_low = frame["low"] < prior_low
    touched_long_fib = (frame["low"] <= fib_line) & (frame["high"] >= fib_line)
    reclaimed_low = frame["close"] > prior_low
    long_candidate = swept_low & touched_long_fib & reclaimed_low
    if p.require_candle_direction:
        long_candidate &= frame["close"] > frame["open"]

    swept_high = frame["high"] > prior_high
    touched_short_fib = (frame["high"] >= fib_line) & (frame["low"] <= fib_line)
    rejected_high = frame["close"] < prior_high
    short_candidate = swept_high & touched_short_fib & rejected_high
    if p.require_candle_direction:
        short_candidate &= frame["close"] < frame["open"]

    raw = pd.Series(0, index=frame.index, dtype=int)
    ambiguous = long_candidate & short_candidate
    raw.loc[long_candidate & ~ambiguous] = 1
    if p.allow_shorts:
        raw.loc[short_candidate & ~ambiguous] = -1

    if p.markov_gate != "off":
        cache_key = (p.markov_window, p.markov_threshold, p.min_train)
        if markov_cache is not None and cache_key in markov_cache:
            ms = markov_cache[cache_key]
        else:
            ms = markov_signal(frame["close"], window=p.markov_window, threshold=p.markov_threshold, min_train=p.min_train)
            if markov_cache is not None:
                markov_cache[cache_key] = ms
        if p.markov_gate == "long_nonnegative":
            raw.loc[(raw == 1) & (ms < 0)] = 0
            raw.loc[(raw == -1) & (ms >= 0)] = 0
        elif p.markov_gate == "directional":
            raw.loc[(raw == 1) & (ms <= 0)] = 0
            raw.loc[(raw == -1) & (ms >= 0)] = 0
        else:
            raise ValueError(p.markov_gate)

    # Setup at close executes at next open, held open-to-open for one bar.
    return raw.shift(1, fill_value=0).astype(int)


def strategy_returns(frame: pd.DataFrame, positions: pd.Series, *, cost: float = ROUND_TRIP_COST) -> pd.Series:
    next_open_return = frame["open"].shift(-1) / frame["open"] - 1.0
    gross = (positions * next_open_return).fillna(0.0).astype(float)
    costs = (positions != 0).astype(float) * cost
    net = gross - costs
    net.iloc[-1] = 0.0
    return net


def metrics(returns: pd.Series, positions: pd.Series, gross_returns: pd.Series | None = None) -> Metrics:
    if gross_returns is None:
        gross_returns = returns
    active = positions != 0
    trade_returns = returns.loc[active]
    gross_trade_returns = gross_returns.loc[active]
    total = float((1 + returns).prod() - 1)
    gross_total = float((1 + gross_returns).prod() - 1)
    years = len(returns) / PERIODS_PER_YEAR
    ann = float((1 + total) ** (1 / years) - 1) if years > 0 and total > -1 else -1.0
    std = float(returns.std(ddof=0))
    sharpe = float((returns.mean() / std) * np.sqrt(PERIODS_PER_YEAR)) if std > 0 else 0.0
    equity = (1 + returns).cumprod()
    dd = equity / equity.cummax() - 1
    wins = int((trade_returns > 0).sum())
    losses = int((trade_returns < 0).sum())
    trades = int(active.sum())
    return Metrics(
        bars=int(len(returns)),
        trades=trades,
        long_trades=int((positions == 1).sum()),
        short_trades=int((positions == -1).sum()),
        wins=wins,
        losses=losses,
        win_rate=float(wins / trades) if trades else 0.0,
        gross_total_return=gross_total,
        net_total_return=total,
        annualized_return=ann,
        sharpe=sharpe,
        max_drawdown=float(dd.min()) if len(dd) else 0.0,
        avg_trade_return_net=float(trade_returns.mean()) if trades else 0.0,
        exposure=float(active.mean()) if len(active) else 0.0,
    )


def buy_hold(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    rets = (frame["open"].shift(-1) / frame["open"] - 1.0).fillna(0.0)
    pos = pd.Series(1, index=frame.index, dtype=int)
    pos.iloc[-1] = 0
    return rets, pos


def markov_only(frame: pd.DataFrame, *, window: int = 20, threshold: float = 0.05, min_train: int = 252) -> tuple[pd.Series, pd.Series]:
    ms = markov_signal(frame["close"], window=window, threshold=threshold, min_train=min_train)
    raw = pd.Series(0, index=frame.index, dtype=int)
    raw.loc[ms > 0] = 1
    raw.loc[ms < 0] = -1
    pos = raw.shift(1, fill_value=0).astype(int)
    gross = (pos * (frame["open"].shift(-1) / frame["open"] - 1.0)).fillna(0.0)
    # Model as daily rebalance directional baseline: 2 bps daily when in market, not 10 bps one-shot event cost.
    net = gross - (pos != 0).astype(float) * 0.0002
    net.iloc[-1] = 0.0
    return net, pos


def split_frame(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    cut = int(len(frame) * TRAIN_FRACTION)
    return frame.iloc[:cut].copy(), frame.iloc[cut:].copy()


def param_grid() -> list[Params]:
    return [
        Params(*vals)
        for vals in product(
            [3, 5, 8, 10, 13, 20, 34],
            [0.382, 0.5, 0.618, 0.786],
            [True, False],
            [False, True],
            ["off", "long_nonnegative", "directional"],
            [20, 40],
            [0.03, 0.05],
            [126, 252],
        )
    ]


def evaluate_param(frame: pd.DataFrame, p: Params, markov_cache: dict[tuple[int, float, int], pd.Series] | None = None) -> tuple[pd.Series, Metrics, Metrics]:
    pos = combo_positions(frame, p, markov_cache=markov_cache)
    next_open_return = frame["open"].shift(-1) / frame["open"] - 1.0
    gross = (pos * next_open_return).fillna(0.0).astype(float)
    net = strategy_returns(frame, pos)
    train, test = split_frame(frame)
    pos_train, pos_test = pos.loc[train.index], pos.loc[test.index]
    gross_train, gross_test = gross.loc[train.index], gross.loc[test.index]
    net_train, net_test = net.loc[train.index], net.loc[test.index]
    return pos, metrics(net_train, pos_train, gross_train), metrics(net_test, pos_test, gross_test)


def main() -> int:
    out_dir = Path("research/nasdaq_combo_fib_liquidity_sweep")
    out_dir.mkdir(parents=True, exist_ok=True)
    data_dir = out_dir / "data"
    data_dir.mkdir(exist_ok=True)

    all_results = []
    summary = {"settings": {"period": PERIOD, "interval": INTERVAL, "train_fraction": TRAIN_FRACTION, "round_trip_cost": ROUND_TRIP_COST}, "assets": {}}

    for symbol in ASSETS:
        try:
            frame = fetch_ohlcv(symbol)
        except Exception as exc:
            summary["assets"][symbol] = {"error": str(exc)}
            continue
        safe = symbol.replace("^", "").replace("=", "_")
        frame.to_csv(data_dir / f"{safe}_ohlcv.csv")
        train, test = split_frame(frame)

        rows = []
        best = None
        best_key = None
        markov_cache: dict[tuple[int, float, int], pd.Series] = {}
        for p in param_grid():
            pos, train_m, test_m = evaluate_param(frame, p, markov_cache=markov_cache)
            row = {
                "symbol": symbol,
                **asdict(p),
                **{f"train_{k}": v for k, v in asdict(train_m).items()},
                **{f"test_{k}": v for k, v in asdict(test_m).items()},
            }
            rows.append(row)
            # Select on train only; require at least moderate train activity to avoid 1-trade overfit.
            eligible = train_m.trades >= 8 and train_m.max_drawdown > -0.25
            key = (train_m.sharpe, train_m.net_total_return, train_m.trades)
            if eligible and (best_key is None or key > best_key):
                best_key = key
                best = (p, pos, train_m, test_m)
        result_frame = pd.DataFrame(rows)
        result_frame.to_csv(out_dir / f"{safe}_sweep.csv", index=False)
        all_results.extend(rows)

        if best is None:
            # fallback: most active variant, then train return
            result_frame["activity_rank"] = result_frame["train_trades"]
            idx = result_frame.sort_values(["train_trades", "train_net_total_return"], ascending=False).index[0]
            chosen_dict = result_frame.loc[idx].to_dict()
            p = Params(
                lookback=int(chosen_dict["lookback"]),
                fib_level=float(chosen_dict["fib_level"]),
                require_candle_direction=bool(chosen_dict["require_candle_direction"]),
                allow_shorts=bool(chosen_dict["allow_shorts"]),
                markov_gate=str(chosen_dict["markov_gate"]),
                markov_window=int(chosen_dict["markov_window"]),
                markov_threshold=float(chosen_dict["markov_threshold"]),
                min_train=int(chosen_dict["min_train"]),
            )
            pos, train_m, test_m = evaluate_param(frame, p, markov_cache=markov_cache)
            best = (p, pos, train_m, test_m)

        p, pos, train_m, test_m = best
        bh_train_rets, bh_train_pos = buy_hold(train)
        bh_test_rets, bh_test_pos = buy_hold(test)
        mo_train_rets, mo_train_pos = markov_only(train)
        mo_test_rets, mo_test_pos = markov_only(test)

        selected_positions = pd.DataFrame({"position": pos}, index=frame.index)
        selected_positions.to_csv(out_dir / f"{safe}_selected_positions.csv")

        summary["assets"][symbol] = {
            "rows": int(len(frame)),
            "start": str(frame.index.min().date()),
            "end": str(frame.index.max().date()),
            "train_start": str(train.index.min().date()),
            "train_end": str(train.index.max().date()),
            "test_start": str(test.index.min().date()),
            "test_end": str(test.index.max().date()),
            "selected_params_train_only": asdict(p),
            "combo_train": asdict(train_m),
            "combo_test": asdict(test_m),
            "buy_hold_train": asdict(metrics(bh_train_rets, bh_train_pos)),
            "buy_hold_test": asdict(metrics(bh_test_rets, bh_test_pos)),
            "markov_only_train": asdict(metrics(mo_train_rets, mo_train_pos)),
            "markov_only_test": asdict(metrics(mo_test_rets, mo_test_pos)),
            "sweep_csv": str(out_dir / f"{safe}_sweep.csv"),
            "selected_positions_csv": str(out_dir / f"{safe}_selected_positions.csv"),
        }

    pd.DataFrame(all_results).to_csv(out_dir / "all_sweep_results.csv", index=False)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
