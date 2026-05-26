from __future__ import annotations

import pandas as pd

from trading_hub.parameter_sweep import run_param_sweep
from trading_hub.hft_evaluator import EvaluationResult


class ThresholdAdapter:
    def __init__(self, *, threshold: float, side: int = 1):
        self.threshold = threshold
        self.side = side

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signal = pd.Series(0, index=data.index, dtype=int)
        signal.loc[data['close'] > self.threshold] = self.side
        return pd.DataFrame({'signal': signal}, index=data.index)


class ZeroAdapter:
    def __init__(self, *, label: str = 'flat'):
        self.label = label

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame({'signal': pd.Series(0, index=data.index, dtype=int)}, index=data.index)


def _ohlcv() -> pd.DataFrame:
    index = pd.date_range('2024-01-01 09:30', periods=6, freq='min')
    close = pd.Series([100.0, 101.0, 99.5, 102.0, 101.5, 103.0], index=index)
    return pd.DataFrame(
        {
            'open': close.shift(1, fill_value=100.0),
            'high': close + 0.5,
            'low': close - 0.5,
            'close': close,
            'volume': [10, 11, 12, 13, 14, 15],
        },
        index=index,
    )


def test_param_sweep_returns_one_row_per_deterministic_parameter_combination_with_metrics():
    result = run_param_sweep(
        _ohlcv(),
        ThresholdAdapter,
        {
            'threshold': [100.5, 102.5],
            'side': [1, -1],
        },
        evaluator_kwargs={'periods_per_year': 365},
    )

    assert result['param_threshold'].tolist() == [100.5, 100.5, 102.5, 102.5]
    assert result['param_side'].tolist() == [1, -1, 1, -1]
    assert result['name'].tolist() == [
        'ThresholdAdapter[0]',
        'ThresholdAdapter[1]',
        'ThresholdAdapter[2]',
        'ThresholdAdapter[3]',
    ]
    for metric_name in ('bars', 'trades', 'net_pnl', 'sharpe', 'pnl_by_regime'):
        assert metric_name in result.columns
    assert result['bars'].tolist() == [6, 6, 6, 6]
    assert result['trades'].tolist()[0] > result['trades'].tolist()[2]


def test_param_sweep_keeps_zero_trade_combinations_with_hft_metric_schema():
    result = run_param_sweep(_ohlcv(), ZeroAdapter, {'label': ['flat']})

    assert len(result) == 1
    assert result.loc[0, 'param_label'] == 'flat'
    assert result.loc[0, 'trades'] == 0
    assert result.loc[0, 'net_pnl'] == 0.0
    assert result.loc[0, 'win_rate'] == 0.0
    assert isinstance(result.loc[0, 'evaluation'], EvaluationResult)


def test_param_sweep_rejects_too_many_combinations_before_running_adapters():
    class ExplodingAdapter:
        def __init__(self, **kwargs: object):
            raise AssertionError('adapter should not be instantiated when max_combinations guard trips')

    try:
        run_param_sweep(
            _ohlcv(),
            ExplodingAdapter,
            {'a': [1, 2], 'b': [3, 4]},
            max_combinations=3,
        )
    except ValueError as exc:
        assert 'max_combinations' in str(exc)
        assert '4' in str(exc)
    else:
        raise AssertionError('expected oversized sweep to raise ValueError')
