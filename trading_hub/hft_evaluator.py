from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd

OrderType = Literal['maker', 'taker']


@dataclass(frozen=True)
class CostModel:
    """Conservative paper-only intraday execution cost assumptions.

    All fields are basis points of notional. Fees are charged per side; spread and
    slippage are also modeled per side so round trips are deliberately
    conservative for research screening.
    """

    maker_fee_bps: float = 2.0
    taker_fee_bps: float = 5.5
    spread_bps: float = 1.0
    slippage_bps: float = 2.0
    order_type: OrderType = 'taker'

    def fee_bps(self) -> float:
        if self.order_type == 'maker':
            return float(self.maker_fee_bps)
        if self.order_type == 'taker':
            return float(self.taker_fee_bps)
        raise ValueError("order_type must be 'maker' or 'taker'")

    def per_side_cost_rate(self) -> float:
        return (self.fee_bps() + self.spread_bps + self.slippage_bps) / 10_000.0

    def round_trip_cost_rate(self) -> float:
        return 2.0 * self.per_side_cost_rate()


@dataclass(frozen=True)
class ExecutionAssumptions:
    """Paper execution knobs for signal-to-fill conversion."""

    latency_bars: int = 1
    hold_bars: int = 1


@dataclass(frozen=True)
class TradeConstraints:
    """Risk throttles used before a signal is allowed into the paper simulator."""

    max_trades_per_day: int | None = None
    cooldown_bars: int = 0


@dataclass(frozen=True)
class WalkForwardConfig:
    """Rolling train/validation/test partition sizes in bars."""

    train_bars: int
    validation_bars: int
    test_bars: int
    step_bars: int | None = None


@dataclass(frozen=True)
class EvaluationResult:
    name: str
    assumptions: dict[str, Any]
    metrics: dict[str, Any]
    trades: pd.DataFrame
    returns: pd.DataFrame
    pnl_by_regime: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'assumptions': self.assumptions,
            'metrics': self.metrics,
            'pnl_by_regime': self.pnl_by_regime,
            'trades': self.trades.to_dict(orient='records'),
        }


@dataclass(frozen=True)
class WalkForwardFold:
    fold: int
    train_start: Any
    train_end: Any
    validation_start: Any
    validation_end: Any
    test_start: Any
    test_end: Any
    train: EvaluationResult
    validation: EvaluationResult
    test: EvaluationResult
    baselines: dict[str, EvaluationResult]


def evaluate_intraday_strategy(
    data: pd.DataFrame,
    signal: pd.Series,
    *,
    name: str = 'strategy',
    cost_model: CostModel | None = None,
    execution: ExecutionAssumptions | None = None,
    constraints: TradeConstraints | None = None,
    regime: pd.Series | None = None,
    periods_per_year: int = 365 * 24 * 60,
) -> EvaluationResult:
    """Evaluate paper-only one-position intraday signals with costs and throttles.

    The input signal is a desired side (-1, 0, +1) known at each bar. It is shifted
    by ``latency_bars`` before any fill, then each accepted trade is held for
    ``hold_bars`` bars and exits at a future open. This intentionally avoids
    same-bar lookahead and is simple enough for research comparability across
    strategy adapters.
    """

    frame = _load_ohlcv(data)
    aligned_signal = _align_signal(signal, frame.index)
    cost = cost_model or CostModel()
    exec_assumptions = execution or ExecutionAssumptions()
    throttle = constraints or TradeConstraints()
    if exec_assumptions.latency_bars < 0:
        raise ValueError('latency_bars must be >= 0')
    if exec_assumptions.hold_bars < 1:
        raise ValueError('hold_bars must be >= 1')
    if throttle.cooldown_bars < 0:
        raise ValueError('cooldown_bars must be >= 0')
    if throttle.max_trades_per_day is not None and throttle.max_trades_per_day < 1:
        raise ValueError('max_trades_per_day must be >= 1 when provided')

    executable = aligned_signal.shift(exec_assumptions.latency_bars, fill_value=0).astype(int)
    net_returns = pd.Series(0.0, index=frame.index)
    gross_returns = pd.Series(0.0, index=frame.index)
    cost_returns = pd.Series(0.0, index=frame.index)
    records: list[dict[str, Any]] = []
    next_allowed_i = 0
    trades_by_day: dict[Any, int] = {}

    for i, timestamp in enumerate(frame.index):
        if i < next_allowed_i:
            continue
        side = int(executable.iloc[i])
        if side == 0:
            continue
        exit_i = i + exec_assumptions.hold_bars
        if exit_i >= len(frame):
            break
        day_key = _day_key(timestamp)
        if throttle.max_trades_per_day is not None and trades_by_day.get(day_key, 0) >= throttle.max_trades_per_day:
            continue
        entry_price = float(frame['open'].iloc[i])
        exit_price = float(frame['open'].iloc[exit_i])
        if entry_price <= 0 or exit_price <= 0:
            continue
        gross = side * (exit_price / entry_price - 1.0)
        cost_rate = cost.round_trip_cost_rate()
        net = gross - cost_rate
        gross_returns.iloc[exit_i] += gross
        cost_returns.iloc[exit_i] += cost_rate
        net_returns.iloc[exit_i] += net
        records.append(
            {
                'entry_time': timestamp,
                'exit_time': frame.index[exit_i],
                'side': side,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'gross_return': gross,
                'cost_return': cost_rate,
                'net_return': net,
                'hold_bars': exec_assumptions.hold_bars,
            }
        )
        trades_by_day[day_key] = trades_by_day.get(day_key, 0) + 1
        next_allowed_i = exit_i + throttle.cooldown_bars + 1

    trades = pd.DataFrame.from_records(
        records,
        columns=[
            'entry_time',
            'exit_time',
            'side',
            'entry_price',
            'exit_price',
            'gross_return',
            'cost_return',
            'net_return',
            'hold_bars',
        ],
    )
    returns = pd.DataFrame({'gross': gross_returns, 'costs': cost_returns, 'net': net_returns}, index=frame.index)
    regime_aligned = _align_regime(regime, frame.index)
    metrics = compute_hft_metrics(
        frame,
        returns,
        trades,
        periods_per_year=periods_per_year,
        regime=regime_aligned,
    )
    return EvaluationResult(
        name=name,
        assumptions={
            'cost_model': asdict(cost),
            'execution': asdict(exec_assumptions),
            'constraints': asdict(throttle),
            'periods_per_year': periods_per_year,
        },
        metrics=metrics,
        trades=trades,
        returns=returns,
        pnl_by_regime=metrics['pnl_by_regime'],
    )


def compute_hft_metrics(
    frame: pd.DataFrame,
    returns: pd.DataFrame,
    trades: pd.DataFrame,
    *,
    periods_per_year: int,
    regime: pd.Series | None = None,
) -> dict[str, Any]:
    net = returns['net'].astype(float) if 'net' in returns else pd.Series(dtype=float)
    gross = returns['gross'].astype(float) if 'gross' in returns else pd.Series(dtype=float)
    costs = returns['costs'].astype(float) if 'costs' in returns else pd.Series(dtype=float)
    trade_net = trades['net_return'].astype(float) if not trades.empty else pd.Series(dtype=float)
    trade_gross = trades['gross_return'].astype(float) if not trades.empty else pd.Series(dtype=float)
    equity = (1.0 + net).cumprod() if len(net) else pd.Series(dtype=float)
    drawdown = equity / equity.cummax() - 1.0 if len(equity) else pd.Series(dtype=float)
    gross_profit = float(trade_gross[trade_gross > 0].sum()) if len(trade_gross) else 0.0
    gross_loss = float(-trade_gross[trade_gross < 0].sum()) if len(trade_gross) else 0.0
    net_profit = float(trade_net[trade_net > 0].sum()) if len(trade_net) else 0.0
    net_loss = float(-trade_net[trade_net < 0].sum()) if len(trade_net) else 0.0
    days = _span_days(frame.index)
    std = float(net.std(ddof=0)) if len(net) else 0.0
    sharpe = float((net.mean() / std) * np.sqrt(periods_per_year)) if std > 0 and periods_per_year > 0 else 0.0
    pnl_by_regime = _pnl_by_regime(net, regime)
    trade_count = int(len(trades))
    return {
        'bars': int(len(frame)),
        'trades': trade_count,
        'long_trades': int((trades['side'] == 1).sum()) if not trades.empty else 0,
        'short_trades': int((trades['side'] == -1).sum()) if not trades.empty else 0,
        'wins': int((trade_net > 0).sum()) if len(trade_net) else 0,
        'losses': int((trade_net < 0).sum()) if len(trade_net) else 0,
        'win_rate': float((trade_net > 0).mean()) if len(trade_net) else 0.0,
        'gross_pnl': float((1.0 + gross).prod() - 1.0) if len(gross) else 0.0,
        'net_pnl': float(equity.iloc[-1] - 1.0) if len(equity) else 0.0,
        'total_costs': float(costs.sum()) if len(costs) else 0.0,
        'ev_per_trade': float(trade_net.mean()) if trade_count else 0.0,
        'median_trade_return': float(trade_net.median()) if trade_count else 0.0,
        'trades_per_day': float(trade_count / days),
        'profit_factor': float(net_profit / net_loss) if net_loss > 0 else (float('inf') if net_profit > 0 else 0.0),
        'gross_profit_factor': float(gross_profit / gross_loss) if gross_loss > 0 else (float('inf') if gross_profit > 0 else 0.0),
        'max_drawdown': float(drawdown.min()) if len(drawdown) else 0.0,
        'sharpe': sharpe,
        'fee_to_gross_profit': float(costs.sum() / gross_profit) if gross_profit > 0 else float('inf'),
        'pnl_by_regime': pnl_by_regime,
    }


def build_baseline_signals(
    data: pd.DataFrame,
    strategy_signal: pd.Series,
    *,
    seed: int = 7,
    vwap_window: int = 60,
) -> dict[str, pd.Series]:
    """Return no-trade, buy-hold, random same-frequency, and naive VWAP signals."""

    frame = _load_ohlcv(data)
    signal = _align_signal(strategy_signal, frame.index)
    rng = np.random.default_rng(seed)
    baselines: dict[str, pd.Series] = {
        'no_trade': pd.Series(0, index=frame.index, dtype=int),
        'buy_hold': pd.Series(1, index=frame.index, dtype=int),
    }
    active_count = int((signal != 0).sum())
    random_signal = pd.Series(0, index=frame.index, dtype=int)
    if active_count:
        chosen = rng.choice(np.arange(len(frame)), size=min(active_count, len(frame)), replace=False)
        long_share = float((signal > 0).mean()) if (signal != 0).any() else 1.0
        random_sides = np.where(rng.random(len(chosen)) < long_share, 1, -1)
        random_signal.iloc[chosen] = random_sides.astype(int)
    baselines['random_same_frequency'] = random_signal
    vwap = rolling_vwap(frame, vwap_window)
    naive = pd.Series(0, index=frame.index, dtype=int)
    naive.loc[frame['close'] < vwap] = 1
    naive.loc[frame['close'] > vwap] = -1
    baselines['naive_vwap_reversion'] = naive.shift(1, fill_value=0).astype(int)
    return baselines


def evaluate_with_baselines(
    data: pd.DataFrame,
    signal: pd.Series,
    *,
    name: str = 'strategy',
    cost_model: CostModel | None = None,
    execution: ExecutionAssumptions | None = None,
    constraints: TradeConstraints | None = None,
    regime: pd.Series | None = None,
    periods_per_year: int = 365 * 24 * 60,
    random_seed: int = 7,
) -> dict[str, EvaluationResult]:
    results = {
        name: evaluate_intraday_strategy(
            data,
            signal,
            name=name,
            cost_model=cost_model,
            execution=execution,
            constraints=constraints,
            regime=regime,
            periods_per_year=periods_per_year,
        )
    }
    for baseline_name, baseline_signal in build_baseline_signals(data, signal, seed=random_seed).items():
        results[baseline_name] = evaluate_intraday_strategy(
            data,
            baseline_signal,
            name=baseline_name,
            cost_model=cost_model,
            execution=execution,
            constraints=constraints,
            regime=regime,
            periods_per_year=periods_per_year,
        )
    return results


def walk_forward_evaluate(
    data: pd.DataFrame,
    signal: pd.Series,
    config: WalkForwardConfig,
    *,
    name: str = 'strategy',
    cost_model: CostModel | None = None,
    execution: ExecutionAssumptions | None = None,
    constraints: TradeConstraints | None = None,
    regime: pd.Series | None = None,
    periods_per_year: int = 365 * 24 * 60,
    random_seed: int = 7,
) -> list[WalkForwardFold]:
    """Evaluate rolling train/validation/test folds without optimizing on test."""

    frame = _load_ohlcv(data)
    aligned_signal = _align_signal(signal, frame.index)
    aligned_regime = _align_regime(regime, frame.index)
    if min(config.train_bars, config.validation_bars, config.test_bars) < 1:
        raise ValueError('train_bars, validation_bars, and test_bars must be positive')
    step = config.step_bars or config.test_bars
    if step < 1:
        raise ValueError('step_bars must be positive')
    folds: list[WalkForwardFold] = []
    window = config.train_bars + config.validation_bars + config.test_bars
    fold_id = 0
    for start in range(0, len(frame) - window + 1, step):
        train_slice = slice(start, start + config.train_bars)
        val_slice = slice(start + config.train_bars, start + config.train_bars + config.validation_bars)
        test_slice = slice(start + config.train_bars + config.validation_bars, start + window)
        train = _evaluate_slice(frame, aligned_signal, train_slice, name, cost_model, execution, constraints, aligned_regime, periods_per_year)
        validation = _evaluate_slice(frame, aligned_signal, val_slice, name, cost_model, execution, constraints, aligned_regime, periods_per_year)
        test = _evaluate_slice(frame, aligned_signal, test_slice, name, cost_model, execution, constraints, aligned_regime, periods_per_year)
        test_frame = frame.iloc[test_slice]
        test_signal = aligned_signal.iloc[test_slice]
        test_regime = aligned_regime.iloc[test_slice] if aligned_regime is not None else None
        baselines = evaluate_with_baselines(
            test_frame,
            test_signal,
            name=name,
            cost_model=cost_model,
            execution=execution,
            constraints=constraints,
            regime=test_regime,
            periods_per_year=periods_per_year,
            random_seed=random_seed + fold_id,
        )
        baselines.pop(name, None)
        folds.append(
            WalkForwardFold(
                fold=fold_id,
                train_start=frame.index[train_slice][0],
                train_end=frame.index[train_slice][-1],
                validation_start=frame.index[val_slice][0],
                validation_end=frame.index[val_slice][-1],
                test_start=frame.index[test_slice][0],
                test_end=frame.index[test_slice][-1],
                train=train,
                validation=validation,
                test=test,
                baselines=baselines,
            )
        )
        fold_id += 1
    return folds


def rolling_vwap(frame: pd.DataFrame, window: int) -> pd.Series:
    typical = (frame['high'] + frame['low'] + frame['close']) / 3.0
    volume = frame['volume'].replace(0, np.nan)
    return (typical * volume).rolling(window, min_periods=window).sum() / volume.rolling(window, min_periods=window).sum()


def _evaluate_slice(
    frame: pd.DataFrame,
    signal: pd.Series,
    row_slice: slice,
    name: str,
    cost_model: CostModel | None,
    execution: ExecutionAssumptions | None,
    constraints: TradeConstraints | None,
    regime: pd.Series | None,
    periods_per_year: int,
) -> EvaluationResult:
    frame_part = frame.iloc[row_slice]
    signal_part = signal.iloc[row_slice]
    regime_part = regime.iloc[row_slice] if regime is not None else None
    return evaluate_intraday_strategy(
        frame_part,
        signal_part,
        name=name,
        cost_model=cost_model,
        execution=execution,
        constraints=constraints,
        regime=regime_part,
        periods_per_year=periods_per_year,
    )


def _load_ohlcv(data: pd.DataFrame) -> pd.DataFrame:
    frame = data.copy()
    rename = {column: str(column).strip().lower().replace(' ', '_') for column in frame.columns}
    frame = frame.rename(columns=rename)
    required = ['open', 'high', 'low', 'close', 'volume']
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f'OHLCV data missing required columns: {missing}')
    frame = frame.loc[:, required].copy()
    for column in required:
        frame[column] = pd.to_numeric(frame[column], errors='coerce')
    frame = frame.dropna(subset=required)
    if frame.empty:
        raise ValueError('OHLCV data has no usable rows')
    if (frame[['open', 'high', 'low', 'close']] <= 0).any().any():
        raise ValueError('OHLC data must be positive')
    if (frame['high'] < frame['low']).any():
        raise ValueError('OHLCV data invalid: high must be greater than or equal to low')
    if not frame.index.is_monotonic_increasing:
        frame = frame.sort_index()
    if isinstance(frame.index, pd.DatetimeIndex):
        frame.index.freq = None
    return frame


def _align_signal(signal: pd.Series, index: pd.Index) -> pd.Series:
    aligned = signal.reindex(index).fillna(0)
    aligned = aligned.clip(lower=-1, upper=1).round().astype(int)
    return aligned


def _align_regime(regime: pd.Series | None, index: pd.Index) -> pd.Series | None:
    if regime is None:
        return None
    return regime.reindex(index).fillna('unknown').astype(str)


def _pnl_by_regime(net_returns: pd.Series, regime: pd.Series | None) -> dict[str, float]:
    if regime is None:
        return {}
    result: dict[str, float] = {}
    for label, values in net_returns.groupby(regime):
        result[str(label)] = float((1.0 + values).prod() - 1.0)
    return result


def _span_days(index: pd.Index) -> float:
    if len(index) < 2:
        return 1.0
    if isinstance(index, pd.DatetimeIndex):
        seconds = (index.max() - index.min()).total_seconds()
        return max(seconds / 86_400.0, 1e-9)
    return max(len(index), 1)


def _day_key(timestamp: Any) -> Any:
    if isinstance(timestamp, pd.Timestamp):
        return timestamp.date()
    return timestamp
