from __future__ import annotations

import pandas as pd
import pytest


def intraday_fixture() -> pd.DataFrame:
    index = pd.date_range('2024-01-01 09:30', periods=16, freq='min')
    close = [100.00, 100.04, 100.08, 100.12, 100.16, 100.20, 100.24, 100.28,
             100.10, 99.90, 99.70, 99.50, 99.30, 99.10, 98.90, 98.70]
    return pd.DataFrame(
        {
            'open': [price - 0.01 for price in close],
            'high': [price + 0.03 for price in close],
            'low': [price - 0.03 for price in close],
            'close': close,
            'volume': [100, 105, 98, 102, 110, 115, 120, 125, 300, 320, 340, 360, 380, 400, 420, 440],
            'spread': [0.01, 0.011, 0.012, 0.011, 0.010, 0.012, 0.013, 0.012, 0.040, 0.045, 0.050, 0.030, 0.020, 0.018, 0.016, 0.015],
            'bid_size': [55, 58, 60, 62, 65, 66, 70, 72, 80, 78, 76, 40, 35, 30, 25, 20],
            'ask_size': [45, 42, 40, 38, 35, 34, 30, 28, 20, 22, 24, 60, 65, 70, 75, 80],
        },
        index=index,
    )


def test_gate_outputs_intraday_features_decisions_and_optimizer_inputs():
    from trading_hub.strategies.intraday_markov_gate import IntradayMarkovRegimeGate

    gate = IntradayMarkovRegimeGate(lookback=4, min_train=4, high_spread_quantile=0.75)
    result = gate.generate(intraday_fixture())

    expected_columns = [
        'return_regime',
        'volatility_regime',
        'spread_regime',
        'volume_regime',
        'vwap_distance_regime',
        'orderbook_imbalance_regime',
        'markov_state',
        'momentum_probability',
        'mean_reversion_probability',
        'selected_strategy',
        'trade_allowed',
        'threshold_multiplier',
        'stop_multiplier',
        'reason',
    ]
    assert list(result.columns) == expected_columns
    assert result['selected_strategy'].iloc[7] == 'momentum'
    assert result['selected_strategy'].iloc[12] == 'mean_reversion'
    assert result['trade_allowed'].iloc[10] is False
    assert result['reason'].iloc[10] == 'blocked_high_spread_regime'
    assert result['threshold_multiplier'].iloc[12] > 1.0
    assert result['stop_multiplier'].iloc[12] < 1.0
    assert result['orderbook_imbalance_regime'].iloc[7] == 'bid_heavy'


def test_gate_is_no_lookahead_when_future_bars_change():
    from trading_hub.strategies.intraday_markov_gate import IntradayMarkovRegimeGate

    base = intraday_fixture()
    changed_future = base.copy()
    changed_future.iloc[13:, changed_future.columns.get_loc('open')] = [119, 120, 121]
    changed_future.iloc[13:, changed_future.columns.get_loc('high')] = [121, 122, 123]
    changed_future.iloc[13:, changed_future.columns.get_loc('low')] = [118, 119, 120]
    changed_future.iloc[13:, changed_future.columns.get_loc('close')] = [120, 121, 122]
    changed_future.iloc[13:, changed_future.columns.get_loc('volume')] = [10_000, 10_000, 10_000]
    changed_future.iloc[13:, changed_future.columns.get_loc('spread')] = [0.50, 0.50, 0.50]
    changed_future.iloc[13:, changed_future.columns.get_loc('bid_size')] = [1, 1, 1]
    changed_future.iloc[13:, changed_future.columns.get_loc('ask_size')] = [100, 100, 100]

    gate = IntradayMarkovRegimeGate(lookback=4, min_train=4)
    base_result = gate.generate(base)
    changed_result = gate.generate(changed_future)

    pd.testing.assert_frame_equal(base_result.iloc[:13], changed_result.iloc[:13])


def test_gate_supports_missing_optional_orderbook_imbalance():
    from trading_hub.strategies.intraday_markov_gate import IntradayMarkovRegimeGate

    df = intraday_fixture().drop(columns=['bid_size', 'ask_size'])
    result = IntradayMarkovRegimeGate(lookback=4, min_train=4).generate(df)

    assert set(result['orderbook_imbalance_regime']) == {'unknown'}
    assert len(result) == len(df)


def test_gate_rejects_invalid_parameters_and_bad_ohlcv():
    from trading_hub.strategies.intraday_markov_gate import IntradayMarkovRegimeGate

    with pytest.raises(ValueError, match='lookback'):
        IntradayMarkovRegimeGate(lookback=1).generate(intraday_fixture())

    df = intraday_fixture()
    df.iloc[0, df.columns.get_loc('low')] = 200
    with pytest.raises(ValueError, match='high must be greater than or equal to low'):
        IntradayMarkovRegimeGate().generate(df)
