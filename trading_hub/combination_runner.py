from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

_SIGNAL_VALUES = {-1, 0, 1}


def build_regime_gated_signal(
    regime_gate: pd.DataFrame,
    signals: dict[str, pd.Series],
    *,
    regime_to_strategy: dict[str, str],
    flat_default: int = 0,
) -> pd.Series:
    """Select one strategy signal per bar from a regime-gate output.

    ``IntradayMarkovRegimeGate.generate()`` emits a ``selected_strategy`` column
    with regime labels such as ``momentum``, ``mean_reversion`` and ``flat``.
    This helper maps those per-bar regime labels to concrete signal series,
    reindexes signals to the gate index, and returns a single research-only
    signal series with the same index and values constrained to -1/0/+1.
    """

    if flat_default != 0:
        raise ValueError('flat_default must be 0; flat/default/disallowed rows must not trade')
    if not isinstance(regime_gate, pd.DataFrame):
        raise TypeError('regime_gate must be a pandas DataFrame')
    if not isinstance(regime_to_strategy, Mapping):
        raise TypeError('regime_to_strategy must be a mapping')
    if any(str(regime_name).lower() in {'flat', 'default'} for regime_name in regime_to_strategy):
        raise ValueError('flat/default regimes must not be mapped to trading strategies')

    index = regime_gate.index
    combined = pd.Series(flat_default, index=index, name='regime_gated_signal', dtype='int8')
    if regime_gate.empty or not regime_to_strategy:
        return combined

    normalized_signals = {
        name: _normalize_signal(signal, index)
        for name, signal in signals.items()
    }

    assigned = pd.Series(False, index=index, dtype=bool)
    selected_strategy = regime_gate.get('selected_strategy')
    trade_allowed = _trade_allowed_mask(regime_gate, index)

    for regime_name, strategy_name in regime_to_strategy.items():
        if strategy_name not in normalized_signals:
            continue
        mask = _regime_mask(regime_gate, selected_strategy, regime_name, index)
        mask = mask & trade_allowed & ~assigned
        if not mask.any():
            continue
        combined.loc[mask] = normalized_signals[strategy_name].loc[mask]
        assigned.loc[mask] = True

    return combined.astype('int8')


def _normalize_signal(signal: pd.Series, index: pd.Index) -> pd.Series:
    if not isinstance(signal, pd.Series):
        signal = pd.Series(signal)
    numeric = pd.Series(pd.to_numeric(signal.reindex(index), errors='coerce'), index=index).fillna(0.0)
    normalized = np.sign(numeric).astype('int8')
    return pd.Series(normalized, index=index, dtype='int8')


def _trade_allowed_mask(regime_gate: pd.DataFrame, index: pd.Index) -> pd.Series:
    if 'trade_allowed' not in regime_gate.columns:
        return pd.Series(True, index=index, dtype=bool)
    return regime_gate['trade_allowed'].reindex(index).fillna(False).astype(bool)


def _regime_mask(
    regime_gate: pd.DataFrame,
    selected_strategy: pd.Series | None,
    regime_name: str,
    index: pd.Index,
) -> pd.Series:
    if selected_strategy is not None:
        return selected_strategy.reindex(index).astype('object').eq(regime_name)
    if regime_name in regime_gate.columns:
        return regime_gate[regime_name].reindex(index).fillna(False).astype(bool)
    return pd.Series(False, index=index, dtype=bool)
