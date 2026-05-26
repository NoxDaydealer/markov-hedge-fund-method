from __future__ import annotations

import math

import pandas as pd
import pytest

from trading_hub.hft_evaluator import (
    CostModel,
    ExecutionAssumptions,
    TradeConstraints,
    WalkForwardConfig,
    build_baseline_signals,
    evaluate_intraday_strategy,
    evaluate_with_baselines,
    walk_forward_evaluate,
)


def hft_fixture(rows: int = 80) -> pd.DataFrame:
    index = pd.date_range('2024-01-01 00:00:00', periods=rows, freq='min')
    open_ = [100.0 + i * 0.1 for i in range(rows)]
    close = [value + 0.05 for value in open_]
    return pd.DataFrame(
        {
            'open': open_,
            'high': [value + 0.2 for value in open_],
            'low': [value - 0.2 for value in open_],
            'close': close,
            'volume': [1000 + (i % 5) * 10 for i in range(rows)],
        },
        index=index,
    )


def test_cost_model_applies_taker_fees_spread_and_slippage_to_trade_ev():
    frame = hft_fixture(10)
    signal = pd.Series(0, index=frame.index)
    signal.iloc[0] = 1
    result = evaluate_intraday_strategy(
        frame,
        signal,
        cost_model=CostModel(taker_fee_bps=5.0, spread_bps=1.0, slippage_bps=2.0, order_type='taker'),
        execution=ExecutionAssumptions(latency_bars=0, hold_bars=1),
    )

    gross = frame['open'].iloc[1] / frame['open'].iloc[0] - 1.0
    round_trip_cost = 2 * (5.0 + 1.0 + 2.0) / 10_000
    assert result.metrics['trades'] == 1
    assert result.trades.loc[0, 'gross_return'] == pytest.approx(gross)
    assert result.trades.loc[0, 'cost_return'] == pytest.approx(round_trip_cost)
    assert result.trades.loc[0, 'net_return'] == pytest.approx(gross - round_trip_cost)
    assert result.metrics['ev_per_trade'] == pytest.approx(gross - round_trip_cost)
    assert result.metrics['fee_to_gross_profit'] == pytest.approx(round_trip_cost / gross)


def test_latency_max_trades_per_day_and_cooldown_throttle_signals():
    frame = hft_fixture(12)
    signal = pd.Series(1, index=frame.index)
    result = evaluate_intraday_strategy(
        frame,
        signal,
        cost_model=CostModel(taker_fee_bps=0.0, spread_bps=0.0, slippage_bps=0.0),
        execution=ExecutionAssumptions(latency_bars=1, hold_bars=1),
        constraints=TradeConstraints(max_trades_per_day=2, cooldown_bars=2),
    )

    assert result.metrics['trades'] == 2
    assert list(result.trades['entry_time']) == [frame.index[1], frame.index[5]]
    assert result.trades.loc[0, 'exit_time'] == frame.index[2]


def test_baselines_include_no_trade_buy_hold_random_same_frequency_and_vwap():
    frame = hft_fixture(90)
    signal = pd.Series(0, index=frame.index)
    signal.iloc[[10, 20, 30, 40]] = [1, -1, 1, -1]
    baselines = build_baseline_signals(frame, signal, seed=123, vwap_window=10)

    assert set(baselines) == {'no_trade', 'buy_hold', 'random_same_frequency', 'naive_vwap_reversion'}
    assert int((baselines['no_trade'] != 0).sum()) == 0
    assert int((baselines['buy_hold'] == 1).sum()) == len(frame)
    assert int((baselines['random_same_frequency'] != 0).sum()) == int((signal != 0).sum())
    assert set(baselines['naive_vwap_reversion'].dropna().unique()).issubset({-1, 0, 1})


def test_evaluate_with_baselines_reports_pnl_by_regime_and_required_metrics():
    frame = hft_fixture(80)
    signal = pd.Series(0, index=frame.index)
    signal.iloc[5::10] = 1
    regime = pd.Series(['trend' if i < 40 else 'chop' for i in range(80)], index=frame.index)
    results = evaluate_with_baselines(
        frame,
        signal,
        name='candidate',
        cost_model=CostModel(taker_fee_bps=0.0, spread_bps=0.0, slippage_bps=0.0),
        execution=ExecutionAssumptions(latency_bars=0, hold_bars=1),
        regime=regime,
    )

    candidate = results['candidate']
    for key in [
        'net_pnl',
        'ev_per_trade',
        'trades_per_day',
        'profit_factor',
        'max_drawdown',
        'fee_to_gross_profit',
        'pnl_by_regime',
    ]:
        assert key in candidate.metrics
    assert set(candidate.pnl_by_regime) == {'trend', 'chop'}
    assert {'no_trade', 'buy_hold', 'random_same_frequency', 'naive_vwap_reversion'}.issubset(results)


def test_walk_forward_evaluate_creates_train_validation_test_folds_with_test_baselines():
    frame = hft_fixture(90)
    signal = pd.Series(0, index=frame.index)
    signal.iloc[::5] = 1
    folds = walk_forward_evaluate(
        frame,
        signal,
        WalkForwardConfig(train_bars=30, validation_bars=10, test_bars=10, step_bars=20),
        cost_model=CostModel(taker_fee_bps=0.0, spread_bps=0.0, slippage_bps=0.0),
        execution=ExecutionAssumptions(latency_bars=0, hold_bars=1),
    )

    assert len(folds) == 3
    assert folds[0].train_start == frame.index[0]
    assert folds[0].validation_start == frame.index[30]
    assert folds[0].test_start == frame.index[40]
    assert set(folds[0].baselines) == {'no_trade', 'buy_hold', 'random_same_frequency', 'naive_vwap_reversion'}
    assert all(not math.isnan(fold.test.metrics['net_pnl']) for fold in folds)
