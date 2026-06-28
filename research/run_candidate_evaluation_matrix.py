from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading_hub.candidate_evaluation_matrix import (
    CandidateSpec,
    DEFAULT_WALK_FORWARD,
    load_ohlcv_csv,
    run_candidate_matrix,
    write_candidate_matrix_reports,
)
from trading_hub.strategies.bollinger_vwap_momentum import BollingerVwapMomentumAdapter
from trading_hub.strategies.vwap_volume_rsi_reversion import VWAPVolumeRSIReversionAdapter

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / 'research' / 'bybit_intraday_strategy_sprint' / 'data'
REPORT_DIR = ROOT / 'research' / 'reports' / 'candidate_evaluation_matrix_20260628'


def build_specs() -> list[CandidateSpec]:
    return [
        CandidateSpec(
            name='vwap_volume_rsi_reversion',
            adapter_factory=VWAPVolumeRSIReversionAdapter,
            param_grid={
                'vwap_window': [20, 40],
                'z_window': [20],
                'rsi_period': [7],
                'stochrsi_period': [7],
                'volume_window': [10],
                'atr_period': [7],
                'z_threshold': [0.50, 0.75, 1.00],
                'volume_multiple': [1.00, 1.25],
                'local_extreme_lookback': [2, 3],
                'enable_shorts': [False],
                'markov_gate': ['off', 'neutral_only'],
            },
        ),
        CandidateSpec(
            name='bollinger_vwap_momentum',
            adapter_factory=BollingerVwapMomentumAdapter,
            param_grid={
                'bb_period': [10, 20],
                'bb_stddev': [2.0],
                'bandwidth_percentile_window': [20, 40],
                'bandwidth_percentile_threshold': [0.20, 0.35, 0.50],
                'volume_window': [10],
                'volume_multiplier': [1.00, 1.25],
                'rsi_period': [7],
                'rsi_long_threshold': [50.0, 55.0],
                'rsi_short_threshold': [45.0],
                'macd_fast': [6],
                'macd_slow': [13],
                'macd_signal': [5],
                'atr_period': [7],
                'enable_shorts': [False],
            },
        ),
    ]


def main() -> None:
    data_by_symbol = {
        'BTCUSDT': load_ohlcv_csv(DATA_DIR / 'BTCUSDT_1m.csv'),
        'ETHUSDT': load_ohlcv_csv(DATA_DIR / 'ETHUSDT_1m.csv'),
    }
    matrix = run_candidate_matrix(
        data_by_symbol,
        build_specs(),
        walk_forward_config=DEFAULT_WALK_FORWARD,
        max_combinations_per_candidate=64,
        min_trades_per_fold=20,
    )
    csv_path, md_path, summary_path = write_candidate_matrix_reports(
        matrix,
        REPORT_DIR,
        '2026-06-28',
    )
    print(f'rows={len(matrix)}')
    print(f'gate_counts={matrix["gate"].value_counts().to_dict()}')
    print(f'csv={csv_path}')
    print(f'md={md_path}')
    print(f'summary={summary_path}')
    print('top5=')
    print(matrix.head(5).to_string(index=False))


if __name__ == '__main__':
    main()
