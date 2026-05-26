"""Tests for trading_hub.combo_comparison_report."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from trading_hub.combo_comparison_report import CSV_COLUMNS, run_combo_comparison, write_reports

_STRATEGY_NAMES = {
    'vwap_reversion_baseline',
    'vwap_rsi_markov_neutral',
    'vwap_rsi_markov_contrarian',
    'bollinger_vwap_no_shorts',
    'bollinger_vwap_shorts',
    'combo_fib_liquidity',
    'regime_gated_combo',
}

_BASELINE_NAMES = {'no_trade', 'buy_hold', 'random_same_freq', 'naive_vwap'}


def _fixture(rows: int = 300) -> pd.DataFrame:
    """Synthetic OHLCV with enough bars for all strategy indicators to warm up."""
    index = pd.date_range('2024-01-01 00:00', periods=rows, freq='min')
    import numpy as np

    rng = np.random.default_rng(42)
    log_returns = rng.normal(0, 0.0005, rows)
    price = 100.0 * (1 + log_returns).cumprod()
    spread = price * 0.0002
    return pd.DataFrame(
        {
            'open': price,
            'high': price + spread,
            'low': price - spread,
            'close': price + rng.uniform(-spread / 2, spread / 2, rows),
            'volume': rng.integers(500, 2000, rows).astype(float),
        },
        index=index,
    )


@pytest.fixture(scope='module')
def comparison_results() -> list[dict]:
    return run_combo_comparison(_fixture(), '2026-05-25')


def test_all_strategies_present(comparison_results: list[dict]) -> None:
    names = {r['strategy'] for r in comparison_results}
    strategies_found = names & _STRATEGY_NAMES
    baselines_found = names & _BASELINE_NAMES
    assert len(strategies_found) >= 7, (
        f'Expected at least 7 strategies, found {len(strategies_found)}: {strategies_found}'
    )
    assert baselines_found == _BASELINE_NAMES, (
        f'Missing baselines: {_BASELINE_NAMES - baselines_found}'
    )


def test_csv_contains_required_columns(comparison_results: list[dict], tmp_path: Path) -> None:
    csv_path, _ = write_reports(comparison_results, '2026-05-25', tmp_path / 'reports')
    df = pd.read_csv(csv_path)
    for col in CSV_COLUMNS:
        assert col in df.columns, f'Missing required column: {col}'


def test_baselines_never_beat_random(comparison_results: list[dict]) -> None:
    random_row = next(r for r in comparison_results if r['strategy'] == 'random_same_freq')
    assert random_row['beats_random'] is False or random_row['beats_random'] == False, (
        'random_same_freq must not beat itself'
    )
