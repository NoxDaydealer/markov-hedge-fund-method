from __future__ import annotations

import socket
from pathlib import Path

import pandas as pd
import pytest


def fixture_ohlcv() -> pd.DataFrame:
    dates = pd.date_range('2024-01-01', periods=12, freq='D')
    return pd.DataFrame(
        {
            'open': [100, 103, 105, 107, 110, 109, 108, 107, 104, 99, 104, 108],
            'high': [104, 106, 108, 111, 112, 110, 109, 108, 105, 109, 109, 111],
            'low': [99, 102, 104, 106, 108, 107, 106, 103, 100, 96, 103, 107],
            'close': [103, 105, 107, 110, 109, 108, 107, 104, 101, 108, 108, 110],
            'volume': [1000, 1100, 1200, 1300, 1250, 1230, 1210, 1400, 1500, 2200, 1800, 1700],
        },
        index=dates,
    )


def test_adapter_accepts_dataframe_and_returns_next_bar_paper_signals():
    from trading_hub.strategies.combo_fib_liquidity import ComboFibLiquidityAdapter

    signals = ComboFibLiquidityAdapter(
        lookback=6,
        atr_period=3,
        markov_signal=0.0,
    ).generate_signals(fixture_ohlcv())

    assert list(signals.columns) == [
        'raw_signal',
        'markov_allowed',
        'signal',
        'execution_signal',
        'execution_price',
        'stop_price',
        'take_profit_price',
        'reason',
    ]
    assert signals['signal'].iloc[9] == 1
    assert signals['execution_signal'].iloc[10] == 1
    assert signals['execution_price'].iloc[10] == pytest.approx(104.0)
    assert signals['execution_signal'].iloc[9] == 0
    assert signals['reason'].iloc[9] == 'long_liquidity_sweep_fib_reclaim'


def test_markov_gate_blocks_longs_in_negative_risk_regime():
    from trading_hub.strategies.combo_fib_liquidity import ComboFibLiquidityAdapter

    signals = ComboFibLiquidityAdapter(
        lookback=6,
        atr_period=3,
        markov_signal=-0.2,
    ).generate_signals(fixture_ohlcv())

    assert signals['raw_signal'].iloc[9] == 1
    assert signals['markov_allowed'].iloc[9] is False
    assert signals['signal'].iloc[9] == 0
    assert signals['execution_signal'].abs().sum() == 0


def test_shorts_disabled_by_default_but_configurable():
    from trading_hub.strategies.combo_fib_liquidity import ComboFibLiquidityAdapter

    df = fixture_ohlcv().copy()
    df.iloc[9, df.columns.get_loc('open')] = 110
    df.iloc[9, df.columns.get_loc('high')] = 114
    df.iloc[9, df.columns.get_loc('low')] = 102
    df.iloc[9, df.columns.get_loc('close')] = 106

    no_shorts = ComboFibLiquidityAdapter(
        lookback=6,
        atr_period=3,
        markov_signal=-0.4,
    ).generate_signals(df)
    shorts_enabled = ComboFibLiquidityAdapter(
        lookback=6,
        atr_period=3,
        markov_signal=-0.4,
        enable_shorts=True,
    ).generate_signals(df)

    assert no_shorts['raw_signal'].iloc[9] == -1
    assert no_shorts['signal'].iloc[9] == 0
    assert shorts_enabled['signal'].iloc[9] == -1
    assert shorts_enabled['execution_signal'].iloc[10] == -1


def test_csv_input_matches_dataframe_output(tmp_path: Path):
    from trading_hub.strategies.combo_fib_liquidity import ComboFibLiquidityAdapter

    df = fixture_ohlcv()
    csv_path = tmp_path / 'ohlcv.csv'
    df.reset_index(names='date').to_csv(csv_path, index=False)

    adapter = ComboFibLiquidityAdapter(lookback=6, atr_period=3, markov_signal=0.0)
    from_df = adapter.generate_signals(df)
    from_csv = adapter.generate_signals(csv_path)

    pd.testing.assert_frame_equal(from_csv, from_df)


def test_adapter_does_not_make_network_calls(monkeypatch):
    from trading_hub.strategies.combo_fib_liquidity import ComboFibLiquidityAdapter

    def fail_network(*args, **kwargs):
        raise AssertionError('network calls are forbidden in paper strategy adapter')

    monkeypatch.setattr(socket, 'create_connection', fail_network)
    monkeypatch.setattr(socket.socket, 'connect', fail_network)

    signals = ComboFibLiquidityAdapter(lookback=6, atr_period=3, markov_signal=0.0).generate_signals(
        fixture_ohlcv()
    )

    assert len(signals) == len(fixture_ohlcv())


def test_no_future_bar_usage_prior_rows_unchanged_when_future_changes():
    from trading_hub.strategies.combo_fib_liquidity import ComboFibLiquidityAdapter

    base = fixture_ohlcv()
    changed_future = base.copy()
    changed_future.iloc[11, changed_future.columns.get_loc('high')] = 999
    changed_future.iloc[11, changed_future.columns.get_loc('low')] = 1
    changed_future.iloc[11, changed_future.columns.get_loc('close')] = 500

    adapter = ComboFibLiquidityAdapter(lookback=6, atr_period=3, markov_signal=0.0)
    base_signals = adapter.generate_signals(base)
    changed_signals = adapter.generate_signals(changed_future)

    pd.testing.assert_frame_equal(base_signals.iloc[:11], changed_signals.iloc[:11])


def test_stable_output_on_fixture_data():
    from trading_hub.strategies.combo_fib_liquidity import ComboFibLiquidityAdapter

    signals = ComboFibLiquidityAdapter(lookback=6, atr_period=3, markov_signal=0.0).generate_signals(
        fixture_ohlcv()
    )

    assert signals['execution_signal'].tolist() == [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0]
    assert signals['signal'].tolist() == [0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0]


def test_fib_zone_must_be_crossed_not_only_liquidity_swept():
    from trading_hub.strategies.combo_fib_liquidity import ComboFibLiquidityAdapter

    df = fixture_ohlcv().copy()
    df.iloc[9, df.columns.get_loc('high')] = 106
    df.iloc[9, df.columns.get_loc('close')] = 106

    signals = ComboFibLiquidityAdapter(lookback=6, atr_period=3, markov_signal=0.0).generate_signals(df)

    assert signals['raw_signal'].iloc[9] == 0
    assert signals['signal'].iloc[9] == 0


def test_ambiguous_same_bar_long_and_short_setup_is_neutral():
    from trading_hub.strategies.combo_fib_liquidity import ComboFibLiquidityAdapter

    df = fixture_ohlcv().copy()
    df.iloc[9, df.columns.get_loc('open')] = 105
    df.iloc[9, df.columns.get_loc('high')] = 114
    df.iloc[9, df.columns.get_loc('low')] = 96
    df.iloc[9, df.columns.get_loc('close')] = 106

    signals = ComboFibLiquidityAdapter(
        lookback=6,
        atr_period=3,
        markov_signal=-0.2,
        enable_shorts=True,
    ).generate_signals(df)

    assert signals['raw_signal'].iloc[9] == 0
    assert signals['signal'].iloc[9] == 0
    assert signals['reason'].iloc[9] == 'ambiguous_long_and_short_setup'


def test_rejects_invalid_risk_parameters():
    from trading_hub.strategies.combo_fib_liquidity import ComboFibLiquidityAdapter

    with pytest.raises(ValueError, match='atr_stop_multiple'):
        ComboFibLiquidityAdapter(atr_stop_multiple=0).generate_signals(fixture_ohlcv())

    with pytest.raises(ValueError, match='markov_signal'):
        ComboFibLiquidityAdapter(markov_signal=float('nan')).generate_signals(fixture_ohlcv())


def test_rejects_invalid_ohlc_rows():
    from trading_hub.strategies.combo_fib_liquidity import ComboFibLiquidityAdapter

    df = fixture_ohlcv().copy()
    df.iloc[0, df.columns.get_loc('high')] = 90

    with pytest.raises(ValueError, match='high must be greater than or equal to low'):
        ComboFibLiquidityAdapter().generate_signals(df)
