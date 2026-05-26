from __future__ import annotations

import pandas as pd

from trading_hub.hft_evaluator import EvaluationResult
from trading_hub.sweeps import (
    run_bollinger_vwap_momentum_sweep,
    run_vwap_rsi_reversion_sweep,
    run_vwap_volume_rsi_reversion_sweep,
)


def _ohlcv(rows: int = 24) -> pd.DataFrame:
    index = pd.date_range('2024-01-01 09:30', periods=rows, freq='min')
    close = pd.Series([100.0 + ((i % 6) - 2) * 0.25 + i * 0.03 for i in range(rows)], index=index)
    open_ = close.shift(1, fill_value=close.iloc[0])
    high = pd.concat([open_, close], axis=1).max(axis=1) + 0.7
    low = pd.concat([open_, close], axis=1).min(axis=1) - 0.7
    return pd.DataFrame(
        {
            'open': open_,
            'high': high,
            'low': low,
            'close': close,
            'volume': [10 + (i % 5) for i in range(rows)],
        },
        index=index,
    )


def test_vwap_volume_rsi_sweep_uses_compact_grid_and_returns_hft_metrics_without_csv(tmp_path):
    output_csv = tmp_path / 'unexpected.csv'

    result = run_vwap_volume_rsi_reversion_sweep(
        _ohlcv(),
        param_grid={
            'vwap_window': [3],
            'z_window': [3],
            'rsi_period': [2],
            'stochrsi_period': [2],
            'volume_window': [2],
            'atr_period': [2],
            'z_threshold': [0.5, 0.75],
            'volume_multiple': [1.0],
            'local_extreme_lookback': [1],
            'enable_shorts': [False],
            'markov_gate': ['off'],
        },
        evaluator_kwargs={'periods_per_year': 365},
    )

    assert len(result) == 2
    assert result['param_z_threshold'].tolist() == [0.5, 0.75]
    assert result.loc[0, 'param_vwap_window'] == 3
    assert result.loc[0, 'param_markov_gate'] == 'off'
    for metric_name in ('bars', 'trades', 'net_pnl', 'sharpe', 'pnl_by_regime'):
        assert metric_name in result.columns
    assert isinstance(result.loc[0, 'evaluation'], EvaluationResult)
    assert not output_csv.exists()


def test_vwap_rsi_short_alias_matches_ultraplan_function_name():
    assert run_vwap_rsi_reversion_sweep is run_vwap_volume_rsi_reversion_sweep


def test_bollinger_vwap_momentum_sweep_writes_csv_only_when_requested(tmp_path):
    output_csv = tmp_path / 'nested' / 'bollinger_sweep.csv'

    result = run_bollinger_vwap_momentum_sweep(
        _ohlcv(),
        param_grid={
            'bb_period': [3],
            'bb_stddev': [1.5, 2.0],
            'bandwidth_percentile_window': [3],
            'bandwidth_percentile_threshold': [0.5],
            'volume_window': [2],
            'volume_multiplier': [1.0],
            'rsi_period': [2],
            'macd_fast': [2],
            'macd_slow': [4],
            'macd_signal': [2],
            'atr_period': [2],
            'enable_shorts': [False],
        },
        output_csv=output_csv,
        evaluator_kwargs={'periods_per_year': 365},
    )

    assert len(result) == 2
    assert result['param_bb_stddev'].tolist() == [1.5, 2.0]
    for metric_name in ('bars', 'trades', 'net_pnl', 'sharpe', 'pnl_by_regime'):
        assert metric_name in result.columns
    assert output_csv.exists()
    csv = pd.read_csv(output_csv)
    assert csv['param_bb_stddev'].tolist() == [1.5, 2.0]
    assert 'evaluation' in csv.columns
