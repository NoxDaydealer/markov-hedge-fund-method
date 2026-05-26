"""Tests for trading_hub.go_no_go_gate."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from trading_hub.go_no_go_gate import GoNoGoResult, add_gate_column_to_results, evaluate_go_no_go
from trading_hub.hft_evaluator import EvaluationResult, WalkForwardFold


def _eval(
    net_pnl: float,
    max_drawdown: float,
    fee_to_gross_profit: float,
    trades: int,
) -> EvaluationResult:
    return EvaluationResult(
        name='test',
        assumptions={},
        metrics={
            'net_pnl': net_pnl,
            'max_drawdown': max_drawdown,
            'fee_to_gross_profit': fee_to_gross_profit,
            'trades': trades,
        },
        trades=pd.DataFrame(),
        returns=pd.DataFrame(),
        pnl_by_regime={},
    )


def _fold(
    net_pnl: float = 0.05,
    max_drawdown: float = -0.10,
    fee_to_gross_profit: float = 0.20,
    trades: int = 30,
    random_pnl: float = 0.01,
    fold_id: int = 0,
) -> WalkForwardFold:
    dummy = _eval(0.0, 0.0, 0.0, 0)
    return WalkForwardFold(
        fold=fold_id,
        train_start=None,
        train_end=None,
        validation_start=None,
        validation_end=None,
        test_start=None,
        test_end=None,
        train=dummy,
        validation=dummy,
        test=_eval(net_pnl, max_drawdown, fee_to_gross_profit, trades),
        baselines={'random_same_frequency': _eval(random_pnl, -0.05, 0.30, trades)},
    )


def test_go_criteria_all_folds_beat_random_and_positive_pnl() -> None:
    folds = [
        _fold(net_pnl=0.05, trades=25, max_drawdown=-0.10, fee_to_gross_profit=0.20, random_pnl=0.01, fold_id=i)
        for i in range(3)
    ]
    result = evaluate_go_no_go(folds)
    assert result.verdict == 'go'
    assert result.reasons_failed == []
    assert result.metrics_summary['avg_net_pnl'] > 0


def test_no_go_high_drawdown() -> None:
    folds = [_fold(net_pnl=0.05, max_drawdown=-0.35, fee_to_gross_profit=0.20, trades=25)]
    result = evaluate_go_no_go(folds)
    assert result.verdict == 'no_go'
    assert any('drawdown' in r.lower() for r in result.reasons_failed)


def test_no_go_fee_threshold() -> None:
    folds = [_fold(net_pnl=0.05, max_drawdown=-0.10, fee_to_gross_profit=0.80, trades=25)]
    result = evaluate_go_no_go(folds)
    assert result.verdict == 'no_go'
    assert any('fee' in r.lower() for r in result.reasons_failed)


def test_no_go_low_trades() -> None:
    folds = [_fold(trades=10)]
    result = evaluate_go_no_go(folds)
    assert result.verdict == 'insufficient_data'
    assert result.reasons_failed


def test_insufficient_data() -> None:
    result = evaluate_go_no_go([])
    assert result.verdict == 'insufficient_data'
    assert result.reasons_failed


def test_gate_column_in_csv(tmp_path: Path) -> None:
    from trading_hub.combo_comparison_report import CSV_COLUMNS, run_combo_comparison, write_reports

    rng = np.random.default_rng(42)
    n = 300
    index = pd.date_range('2024-01-01 00:00', periods=n, freq='min')
    price = 100.0 * (1 + rng.normal(0, 0.0005, n)).cumprod()
    spread = price * 0.0002
    ohlcv = pd.DataFrame(
        {
            'open': price,
            'high': price + spread,
            'low': price - spread,
            'close': price + rng.uniform(-spread / 2, spread / 2, n),
            'volume': rng.integers(500, 2000, n).astype(float),
        },
        index=index,
    )

    rows = run_combo_comparison(ohlcv, '2026-05-25')
    assert 'gate' in CSV_COLUMNS
    assert all('gate' in r for r in rows)
    assert all(r['gate'] in ('go', 'no_go', 'insufficient_data') for r in rows)

    csv_path, _ = write_reports(rows, '2026-05-25', tmp_path / 'reports')
    df = pd.read_csv(csv_path)
    assert 'gate' in df.columns
