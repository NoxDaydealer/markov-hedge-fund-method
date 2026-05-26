from __future__ import annotations

import pandas as pd

from trading_hub.combo_signal import RegimeGatedComboConfig, build_regime_gated_combo_signal


def _idx(n: int = 3) -> pd.DatetimeIndex:
    return pd.date_range('2024-01-02 09:30', periods=n, freq='min')


def _gate(
    regimes: list[str],
    trade_allowed: list[bool] | None = None,
    spread_regime: list[str] | None = None,
    index: pd.DatetimeIndex | None = None,
) -> pd.DataFrame:
    if index is None:
        index = _idx(len(regimes))
    data: dict = {'regime': regimes}
    if trade_allowed is not None:
        data['trade_allowed'] = trade_allowed
    if spread_regime is not None:
        data['spread_regime'] = spread_regime
    return pd.DataFrame(data, index=index)


def test_regime_reversion_passes_reversion_signal():
    index = _idx(3)
    gate = _gate(['mean_reversion', 'mean_reversion', 'mean_reversion'], [True, True, True], index=index)
    reversion = pd.Series([1, -1, 0], index=index)
    momentum = pd.Series([-1, 1, 1], index=index)

    result = build_regime_gated_combo_signal(gate, reversion, momentum)

    expected = pd.Series([1, -1, 0], index=index, name='regime_gated_combo_signal', dtype='int8')
    pd.testing.assert_series_equal(result, expected)


def test_regime_momentum_passes_momentum_signal():
    index = _idx(3)
    gate = _gate(['momentum', 'momentum', 'momentum'], [True, True, True], index=index)
    reversion = pd.Series([-1, 1, 0], index=index)
    momentum = pd.Series([1, -1, 1], index=index)

    result = build_regime_gated_combo_signal(gate, reversion, momentum)

    expected = pd.Series([1, -1, 1], index=index, name='regime_gated_combo_signal', dtype='int8')
    pd.testing.assert_series_equal(result, expected)


def test_regime_flat_returns_zero():
    index = _idx(4)
    gate = _gate(['flat', 'flat', 'unknown', 'high_spread'], [True, True, True, True], index=index)
    reversion = pd.Series([1, 1, 1, 1], index=index)
    momentum = pd.Series([1, 1, 1, 1], index=index)

    result = build_regime_gated_combo_signal(gate, reversion, momentum)

    assert (result == 0).all(), f'expected all zeros, got {result.tolist()}'


def test_regime_high_spread_blocked():
    index = _idx(2)
    gate = _gate(
        ['mean_reversion', 'momentum'],
        [True, True],
        ['high', 'high'],
        index=index,
    )
    reversion = pd.Series([1, 1], index=index)
    momentum = pd.Series([1, 1], index=index)

    # Default config: blocked_when_high_spread=True → all zero despite tradeable regimes
    result = build_regime_gated_combo_signal(gate, reversion, momentum)
    assert (result == 0).all(), 'high spread must block regardless of regime'

    # With blocked_when_high_spread=False: spread does not block
    config = RegimeGatedComboConfig(blocked_when_high_spread=False)
    result_unblocked = build_regime_gated_combo_signal(gate, reversion, momentum, config)
    assert (result_unblocked != 0).all(), 'without spread-block, tradeable regimes should pass through'


def test_signalkollision_reversion_wins():
    index = _idx(1)
    gate = _gate(['mean_reversion'], [True], index=index)
    reversion = pd.Series([1], index=index)   # long
    momentum = pd.Series([-1], index=index)   # short — collision with opposite side

    result = build_regime_gated_combo_signal(gate, reversion, momentum)

    assert result.iloc[0] == 1, f'reversion must win collision, got {result.iloc[0]}'


def test_trade_allowed_false_returns_zero():
    index = _idx(3)
    gate = _gate(
        ['mean_reversion', 'momentum', 'mean_reversion'],
        [False, False, True],
        index=index,
    )
    reversion = pd.Series([1, 1, 1], index=index)
    momentum = pd.Series([1, 1, 1], index=index)

    result = build_regime_gated_combo_signal(gate, reversion, momentum)

    expected = pd.Series([0, 0, 1], index=index, name='regime_gated_combo_signal', dtype='int8')
    pd.testing.assert_series_equal(result, expected)


def test_no_lookahead_behavior():
    # The function must NOT apply any additional bar-shift.
    # Adapters already shift signals by 1 bar; combo_signal passes them through as-is.
    # gate[t] regime → result[t] == signal[t], not signal[t-1].
    index = _idx(4)
    gate = pd.DataFrame(
        {
            'regime': ['mean_reversion', 'mean_reversion', 'momentum', 'momentum'],
            'trade_allowed': [True, True, True, True],
        },
        index=index,
    )
    # Only bar 1 carries a reversion signal; only bar 2 carries a momentum signal
    reversion = pd.Series([0, 1, 0, 0], index=index)
    momentum = pd.Series([0, 0, -1, 0], index=index)

    result = build_regime_gated_combo_signal(gate, reversion, momentum)

    expected = pd.Series([0, 1, -1, 0], index=index, name='regime_gated_combo_signal', dtype='int8')
    pd.testing.assert_series_equal(result, expected)
