from __future__ import annotations

import pandas as pd

from trading_hub.combination_runner import build_regime_gated_signal


def test_regime_gated_signal_selects_non_overlapping_strategy_signals_per_bar():
    index = pd.date_range('2024-01-01 09:30', periods=5, freq='min')
    regime_gate = pd.DataFrame(
        {
            'selected_strategy': ['mean_reversion', 'momentum', 'flat', 'momentum', 'mean_reversion'],
            'trade_allowed': [True, True, True, True, True],
        },
        index=index,
    )
    signals = {
        'mean_reversion': pd.Series([1, 1, 1, -1, -1], index=index),
        'momentum': pd.Series([-1, -1, 1, 1, -1], index=index),
    }

    combined = build_regime_gated_signal(
        regime_gate,
        signals,
        regime_to_strategy={'mean_reversion': 'mean_reversion', 'momentum': 'momentum'},
    )

    expected = pd.Series([1, -1, 0, 1, -1], index=index, name='regime_gated_signal', dtype='int8')
    pd.testing.assert_series_equal(combined, expected)
    assert set(combined.unique()) <= {-1, 0, 1}


def test_regime_gated_signal_preserves_gate_index_and_reindexes_inputs():
    gate_index = pd.date_range('2024-01-01 09:30', periods=4, freq='min')
    signal_index = gate_index[1:]
    regime_gate = pd.DataFrame({'selected_strategy': ['momentum', 'momentum', 'mean_reversion', 'momentum']}, index=gate_index)
    signals = {
        'momentum': pd.Series([1, -1, 1], index=signal_index),
        'mean_reversion': pd.Series([-1, -1, -1], index=signal_index),
    }

    combined = build_regime_gated_signal(
        regime_gate,
        signals,
        regime_to_strategy={'momentum': 'momentum', 'mean_reversion': 'mean_reversion'},
    )

    expected = pd.Series([0, 1, -1, 1], index=gate_index, name='regime_gated_signal', dtype='int8')
    pd.testing.assert_series_equal(combined, expected)
    assert combined.index.equals(gate_index)


def test_regime_gated_signal_uses_mapping_order_as_conflict_priority():
    index = pd.date_range('2024-01-01 09:30', periods=3, freq='min')
    regime_gate = pd.DataFrame(
        {
            'mean_reversion': [True, True, False],
            'momentum': [True, False, True],
        },
        index=index,
    )
    signals = {
        'mean_reversion': pd.Series([-1, -1, -1], index=index),
        'momentum': pd.Series([1, 1, 1], index=index),
    }

    combined = build_regime_gated_signal(
        regime_gate,
        signals,
        regime_to_strategy={'mean_reversion': 'mean_reversion', 'momentum': 'momentum'},
    )

    expected = pd.Series([-1, -1, 1], index=index, name='regime_gated_signal', dtype='int8')
    pd.testing.assert_series_equal(combined, expected)


def test_regime_gated_signal_flattens_explicit_flat_and_disallowed_rows():
    index = pd.date_range('2024-01-01 09:30', periods=4, freq='min')
    regime_gate = pd.DataFrame(
        {
            'selected_strategy': ['flat', 'momentum', 'mean_reversion', 'unknown'],
            'trade_allowed': [True, False, True, True],
        },
        index=index,
    )
    signals = {
        'momentum': pd.Series([1, 1, 1, 1], index=index),
        'mean_reversion': pd.Series([-1, -1, -1, -1], index=index),
    }

    combined = build_regime_gated_signal(
        regime_gate,
        signals,
        regime_to_strategy={'momentum': 'momentum', 'mean_reversion': 'mean_reversion'},
    )

    expected = pd.Series([0, 0, -1, 0], index=index, name='regime_gated_signal', dtype='int8')
    pd.testing.assert_series_equal(combined, expected)


def test_regime_gated_signal_rejects_nonzero_flat_default_to_prevent_default_trades():
    index = pd.date_range('2024-01-01 09:30', periods=2, freq='min')
    regime_gate = pd.DataFrame(
        {'selected_strategy': ['flat', 'momentum'], 'trade_allowed': [True, False]},
        index=index,
    )

    try:
        build_regime_gated_signal(
            regime_gate,
            {'momentum': pd.Series([1, 1], index=index)},
            regime_to_strategy={'momentum': 'momentum'},
            flat_default=1,
        )
    except ValueError as exc:
        assert 'flat/default/disallowed rows must not trade' in str(exc)
    else:
        raise AssertionError('nonzero flat_default should be rejected')


def test_regime_gated_signal_rejects_flat_regime_mapping_to_prevent_flat_trades():
    index = pd.date_range('2024-01-01 09:30', periods=2, freq='min')
    regime_gate = pd.DataFrame({'selected_strategy': ['flat', 'momentum']}, index=index)

    try:
        build_regime_gated_signal(
            regime_gate,
            {'momentum': pd.Series([1, 1], index=index)},
            regime_to_strategy={'flat': 'momentum', 'momentum': 'momentum'},
        )
    except ValueError as exc:
        assert 'flat/default regimes must not be mapped' in str(exc)
    else:
        raise AssertionError('flat regime mapping should be rejected')


def test_regime_gated_signal_handles_empty_and_constant_zero_inputs():
    empty_gate = pd.DataFrame({'selected_strategy': []}, index=pd.DatetimeIndex([]))
    empty = build_regime_gated_signal(
        empty_gate,
        {},
        regime_to_strategy={'momentum': 'momentum'},
    )
    expected_empty = pd.Series([], index=empty_gate.index, name='regime_gated_signal', dtype='int8')
    pd.testing.assert_series_equal(empty, expected_empty)

    index = pd.date_range('2024-01-01 09:30', periods=3, freq='min')
    zero_gate = pd.DataFrame({'selected_strategy': ['momentum', 'momentum', 'flat']}, index=index)
    zero_signal = pd.Series([0, 0, 0], index=index)
    combined = build_regime_gated_signal(
        zero_gate,
        {'momentum': zero_signal},
        regime_to_strategy={'momentum': 'momentum'},
    )

    expected = pd.Series([0, 0, 0], index=index, name='regime_gated_signal', dtype='int8')
    pd.testing.assert_series_equal(combined, expected)
