from __future__ import annotations

import pandas as pd

from trading_hub.candidate_evaluation_matrix import (
    CandidateSpec,
    load_ohlcv_csv,
    run_candidate_matrix,
    write_candidate_matrix_reports,
)
from trading_hub.hft_evaluator import WalkForwardConfig


class ThresholdAdapter:
    def __init__(self, *, threshold: float, side: int = 1):
        self.threshold = threshold
        self.side = side

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signal = pd.Series(0, index=data.index, dtype=int)
        signal.loc[data['close'] > self.threshold] = self.side
        return pd.DataFrame({'signal': signal}, index=data.index)


def _ohlcv(rows: int = 90) -> pd.DataFrame:
    index = pd.date_range('2024-01-01 00:00', periods=rows, freq='min')
    close = pd.Series([100.0 + (i % 9) * 0.15 + i * 0.01 for i in range(rows)], index=index)
    return pd.DataFrame(
        {
            'open': close.shift(1, fill_value=100.0),
            'high': close + 0.3,
            'low': close - 0.3,
            'close': close,
            'volume': [1000.0 + (i % 5) * 50.0 for i in range(rows)],
        },
        index=index,
    )


def test_candidate_matrix_evaluates_all_symbols_and_parameter_combinations():
    matrix = run_candidate_matrix(
        {'AAA': _ohlcv(), 'BBB': _ohlcv()},
        [
            CandidateSpec(
                name='threshold',
                adapter_factory=ThresholdAdapter,
                param_grid={'threshold': [100.4, 100.9], 'side': [1]},
            )
        ],
        walk_forward_config=WalkForwardConfig(train_bars=20, validation_bars=10, test_bars=10, step_bars=10),
        min_trades_per_fold=1,
    )

    assert len(matrix) == 4
    assert set(matrix['symbol']) == {'AAA', 'BBB'}
    assert set(matrix['candidate']) == {'threshold'}
    assert set(matrix['folds']) == {6}
    assert {'go', 'no_go', 'insufficient_data'} >= set(matrix['gate'])
    for required in ('full_net_pnl', 'avg_test_net_pnl', 'reasons_failed', 'fraction_folds_beat_random'):
        assert required in matrix.columns


def test_candidate_matrix_rejects_oversized_grids_before_running():
    try:
        run_candidate_matrix(
            {'AAA': _ohlcv()},
            [CandidateSpec('threshold', ThresholdAdapter, {'threshold': [1, 2, 3], 'side': [1, -1]})],
            max_combinations_per_candidate=5,
        )
    except ValueError as exc:
        assert 'exceeding max_combinations_per_candidate=5' in str(exc)
    else:
        raise AssertionError('expected oversized grid to fail')


def test_candidate_matrix_writes_csv_markdown_and_summary(tmp_path):
    matrix = run_candidate_matrix(
        {'AAA': _ohlcv()},
        [CandidateSpec('threshold', ThresholdAdapter, {'threshold': [100.4], 'side': [1]})],
        walk_forward_config=WalkForwardConfig(train_bars=20, validation_bars=10, test_bars=10, step_bars=10),
        min_trades_per_fold=1,
    )

    csv_path, md_path, summary_path = write_candidate_matrix_reports(matrix, tmp_path, '2026-06-28')

    assert csv_path.exists()
    assert md_path.exists()
    assert summary_path.exists()
    assert 'Trading Hub Candidate Evaluation Matrix' in md_path.read_text(encoding='utf-8')
    assert 'live trading remains locked' in summary_path.read_text(encoding='utf-8')


def test_load_ohlcv_csv_accepts_timestamp_column(tmp_path):
    path = tmp_path / 'bars.csv'
    path.write_text(
        'timestamp,open,high,low,close,volume\n'
        '2024-01-01 00:00:00,1,2,0.5,1.5,10\n',
        encoding='utf-8',
    )

    frame = load_ohlcv_csv(path)

    assert list(frame.columns) == ['open', 'high', 'low', 'close', 'volume']
    assert isinstance(frame.index, pd.DatetimeIndex)
