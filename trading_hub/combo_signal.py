from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RegimeGatedComboConfig:
    mean_reversion_regime: str = 'mean_reversion'
    momentum_regime: str = 'momentum'
    blocked_when_high_spread: bool = True


def build_regime_gated_combo_signal(
    gate_output: pd.DataFrame,
    reversion_signal: pd.Series,
    momentum_signal: pd.Series,
    config: RegimeGatedComboConfig | None = None,
) -> pd.Series:
    """Select between reversion and momentum signals bar-by-bar via Markov regime gate.

    Returns pd.Series {-1, 0, +1} with same index as gate_output.
    Input signals must already be 1-bar shifted by their adapters (no lookahead here).
    When both signals conflict on the same bar, reversion wins.
    """
    if config is None:
        config = RegimeGatedComboConfig()

    index = gate_output.index
    result = pd.Series(0, index=index, name='regime_gated_combo_signal', dtype='int8')
    if gate_output.empty:
        return result

    rev = _normalize(reversion_signal, index)
    mom = _normalize(momentum_signal, index)

    # Rule 1: trade_allowed=False → 0
    allowed = _trade_allowed(gate_output, index)
    # blocked_when_high_spread: additionally block when spread_regime='high'
    if config.blocked_when_high_spread:
        allowed = allowed & ~_high_spread(gate_output, index)

    regime = _regime_col(gate_output, index)

    # Rule 2: mean_reversion regime → reversion_signal
    rev_mask = allowed & regime.eq(config.mean_reversion_regime)
    result.loc[rev_mask] = rev.loc[rev_mask]

    # Rule 3: momentum regime → momentum_signal
    # Note: rev_mask and mom_mask are regime-disjoint (mean_reversion vs momentum),
    # so structurally no collision can occur on a given bar.
    mom_mask = allowed & regime.eq(config.momentum_regime)
    result.loc[mom_mask] = mom.loc[mom_mask]

    # Rule 4: any other regime → 0 (default already set)

    return result.astype('int8')


def _normalize(signal: pd.Series, index: pd.Index) -> pd.Series:
    s = pd.to_numeric(signal.reindex(index), errors='coerce').fillna(0.0)
    return pd.Series(np.sign(s).astype('int8'), index=index, dtype='int8')


def _trade_allowed(gate_output: pd.DataFrame, index: pd.Index) -> pd.Series:
    if 'trade_allowed' not in gate_output.columns:
        return pd.Series(True, index=index, dtype=bool)
    return gate_output['trade_allowed'].reindex(index).fillna(False).astype(bool)


def _high_spread(gate_output: pd.DataFrame, index: pd.Index) -> pd.Series:
    if 'spread_regime' not in gate_output.columns:
        return pd.Series(False, index=index, dtype=bool)
    return gate_output['spread_regime'].reindex(index).eq('high')


def _regime_col(gate_output: pd.DataFrame, index: pd.Index) -> pd.Series:
    for col in ('regime', 'selected_strategy'):
        if col in gate_output.columns:
            return gate_output[col].reindex(index).astype('object')
    return pd.Series(None, index=index, dtype='object')
