"""Go/No-Go gate: evaluates walk-forward folds or single result rows against fitness thresholds."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class GoNoGoResult:
    verdict: Literal['go', 'no_go', 'insufficient_data']
    reasons_failed: list[str]
    metrics_summary: dict[str, float]


def evaluate_go_no_go(
    folds: list,
    *,
    min_trades_per_fold: int = 20,
    max_drawdown_threshold: float = -0.30,
    fee_to_gross_profit_max: float = 0.50,
    min_fraction_folds_beat_random: float = 0.60,
) -> GoNoGoResult:
    """Evaluate a list of WalkForwardFold objects and return a structured Go/No-Go verdict.

    GO:   net_pnl > 0 on all test folds, >= min_trades_per_fold trades per fold,
          max_drawdown >= threshold, fee_to_gross_profit <= max, and
          >= min_fraction_folds_beat_random folds beat the random baseline.
    INSUFFICIENT_DATA: low trade count is the *only* failure reason.
    NO_GO: any other criterion fails (may also include low trade count).
    """
    if not folds:
        return GoNoGoResult(
            verdict='insufficient_data',
            reasons_failed=['no folds provided'],
            metrics_summary={},
        )

    test_pnls = [fold.test.metrics['net_pnl'] for fold in folds]
    test_drawdowns = [fold.test.metrics['max_drawdown'] for fold in folds]
    test_fee_ratios = [fold.test.metrics['fee_to_gross_profit'] for fold in folds]
    test_trades = [fold.test.metrics['trades'] for fold in folds]

    reasons: list[str] = []

    low_trade_count = sum(1 for t in test_trades if t < min_trades_per_fold)
    if low_trade_count:
        reasons.append(f'{low_trade_count} fold(s) have fewer than {min_trades_per_fold} trades')

    negative_pnl_count = sum(1 for p in test_pnls if p <= 0)
    if negative_pnl_count:
        reasons.append(f'{negative_pnl_count} fold(s) have non-positive net_pnl')

    worst_drawdown = min(test_drawdowns)
    if worst_drawdown < max_drawdown_threshold:
        reasons.append(
            f'max_drawdown {worst_drawdown:.4f} exceeds threshold {max_drawdown_threshold}'
        )

    worst_fee_ratio = max(test_fee_ratios)
    if worst_fee_ratio > fee_to_gross_profit_max:
        reasons.append(
            f'fee_to_gross_profit {worst_fee_ratio:.4f} exceeds max {fee_to_gross_profit_max}'
        )

    beats_random_count = sum(
        1 for fold in folds
        if fold.test.metrics['net_pnl'] > (
            fold.baselines['random_same_frequency'].metrics['net_pnl']
            if 'random_same_frequency' in fold.baselines
            else 0.0
        )
    )
    fraction_beat_random = beats_random_count / len(folds)
    if fraction_beat_random < min_fraction_folds_beat_random:
        reasons.append(
            f'only {fraction_beat_random:.1%} of folds beat random baseline'
            f' (need {min_fraction_folds_beat_random:.1%})'
        )

    metrics_summary = {
        'avg_net_pnl': sum(test_pnls) / len(test_pnls),
        'worst_drawdown': float(worst_drawdown),
        'worst_fee_to_gross_profit': float(worst_fee_ratio),
        'avg_trades': sum(test_trades) / len(test_trades),
        'fraction_folds_beat_random': fraction_beat_random,
    }

    if not reasons:
        return GoNoGoResult(verdict='go', reasons_failed=[], metrics_summary=metrics_summary)

    # Low trades as the sole failure → insufficient_data; any other failure present → no_go
    if low_trade_count and len(reasons) == 1:
        return GoNoGoResult(
            verdict='insufficient_data', reasons_failed=reasons, metrics_summary=metrics_summary
        )

    return GoNoGoResult(verdict='no_go', reasons_failed=reasons, metrics_summary=metrics_summary)


def add_gate_column_to_results(results: list[dict]) -> list[dict]:
    """Append a 'gate' key to each result row using single-fold threshold evaluation."""
    return [{**row, 'gate': _single_row_verdict(row)} for row in results]


def _single_row_verdict(
    row: dict,
    *,
    max_drawdown_threshold: float = -0.30,
    fee_to_gross_profit_max: float = 0.50,
    min_trades: int = 20,
) -> str:
    if row.get('trades', 0) < min_trades:
        return 'insufficient_data'
    if row.get('net_pnl', 0.0) <= 0:
        return 'no_go'
    if row.get('max_drawdown', 0.0) < max_drawdown_threshold:
        return 'no_go'
    if row.get('fee_to_gross_profit', float('inf')) > fee_to_gross_profit_max:
        return 'no_go'
    if not row.get('beats_random', False):
        return 'no_go'
    return 'go'
