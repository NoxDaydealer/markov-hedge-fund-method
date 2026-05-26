from __future__ import annotations

import socket

import pandas as pd
import pytest


def fixture_1m_ohlcv() -> pd.DataFrame:
    index = pd.date_range('2024-01-01 00:00:00', periods=18, freq='min')
    return pd.DataFrame(
        {
            'open': [110, 111, 112, 113, 114, 113, 112, 100, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108],
            'high': [111, 112, 113, 114, 115, 114, 113, 100, 102, 102, 103, 104, 105, 106, 107, 108, 109, 110],
            'low': [109, 110, 111, 112, 113, 112, 111, 98, 95, 99, 100, 101, 102, 103, 104, 105, 106, 107],
            'close': [111, 112, 113, 114, 113, 112, 111, 99, 101, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            'volume': [1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 2600, 1200, 1100, 1000, 1000, 1000, 1000, 1000, 1000, 1000],
        },
        index=index,
    )


def test_adapter_generates_next_bar_long_after_vwap_rsi_volume_reclaim():
    from trading_hub.strategies.vwap_volume_reversion import VWAPVolumeReversionAdapter

    signals = VWAPVolumeReversionAdapter(
        vwap_window=5,
        z_window=2,
        rsi_period=3,
        stochrsi_period=3,
        volume_window=4,
        atr_period=3,
        z_threshold=0.5,
        rsi_long=45,
        stochrsi_long=0.8,
        volume_multiple=2.0,
        enable_shorts=False,
    ).generate_signals(fixture_1m_ohlcv())

    assert list(signals.columns) == [
        'vwap',
        'vwap_distance',
        'vwap_distance_zscore',
        'rsi',
        'stochrsi',
        'volume_spike',
        'raw_signal',
        'signal',
        'execution_signal',
        'execution_price',
        'atr',
        'stop_price',
        'target_price',
        'reason',
    ]
    assert signals['raw_signal'].iloc[8] == 1
    assert signals['signal'].iloc[8] == 1
    assert signals['execution_signal'].iloc[8] == 0
    assert signals['execution_signal'].iloc[9] == 1
    assert signals['execution_price'].iloc[9] == pytest.approx(100.0)
    assert signals['volume_spike'].iloc[8] is True
    assert signals['reason'].iloc[8] == 'long_vwap_volume_rsi_reclaim'


def test_adapter_uses_optional_5m_filter_without_network(monkeypatch):
    from trading_hub.strategies.vwap_volume_reversion import VWAPVolumeReversionAdapter

    def fail_network(*args, **kwargs):
        raise AssertionError('network calls are forbidden in local strategy adapter')

    monkeypatch.setattr(socket, 'create_connection', fail_network)
    monkeypatch.setattr(socket.socket, 'connect', fail_network)

    df = fixture_1m_ohlcv()
    five_min = df.resample('5min').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}).dropna()
    signals = VWAPVolumeReversionAdapter(
        vwap_window=5,
        z_window=2,
        rsi_period=3,
        stochrsi_period=3,
        volume_window=4,
        atr_period=3,
        z_threshold=0.5,
        rsi_long=45,
        stochrsi_long=0.8,
        volume_multiple=2.0,
        informative_5m=five_min,
        five_min_rsi_long=55,
    ).generate_signals(df)

    assert len(signals) == len(df)
    assert signals['raw_signal'].iloc[8] == 1


def test_backtest_exits_at_vwap_target_and_applies_cost_hooks():
    from trading_hub.vwap_volume_reversion_backtest import run_vwap_volume_reversion_backtest

    result = run_vwap_volume_reversion_backtest(
        fixture_1m_ohlcv(),
        vwap_window=5,
        z_window=2,
        rsi_period=3,
        stochrsi_period=3,
        volume_window=4,
        atr_period=3,
        z_threshold=0.5,
        rsi_long=45,
        stochrsi_long=0.8,
        volume_multiple=2.0,
        atr_target_multiple=10.0,
        atr_stop_multiple=1.0,
        max_hold_bars=6,
        fee_bps=1.0,
        spread_bps=2.0,
        slippage_bps=3.0,
    )

    assert result.strategy == 'vwap_volume_reversion_v0'
    assert result.metrics['trades'] == 1
    trade = result.trades.iloc[0]
    assert trade['entry_time'] == pd.Timestamp('2024-01-01 00:09:00')
    assert trade['side'] == 1
    assert trade['exit_reason'] == 'vwap_target'
    assert trade['gross_return'] > trade['net_return']
    assert trade['cost_return'] == pytest.approx(0.0006)
    assert result.metrics['gross_total_return'] > result.metrics['net_total_return']


def test_backtest_supports_atr_stop_and_time_stop_paths():
    from trading_hub.vwap_volume_reversion_backtest import run_vwap_volume_reversion_backtest

    stop_df = fixture_1m_ohlcv()
    stop_df.iloc[10, stop_df.columns.get_loc('low')] = 96
    stop_result = run_vwap_volume_reversion_backtest(
        stop_df,
        vwap_window=5,
        z_window=2,
        rsi_period=3,
        stochrsi_period=3,
        volume_window=4,
        atr_period=3,
        z_threshold=0.5,
        rsi_long=45,
        stochrsi_long=0.8,
        volume_multiple=2.0,
        atr_target_multiple=10.0,
        atr_stop_multiple=0.5,
        max_hold_bars=6,
    )
    assert stop_result.trades.iloc[0]['exit_reason'] == 'atr_or_local_extreme_stop'

    time_df = fixture_1m_ohlcv()
    time_df.iloc[10, time_df.columns.get_loc('high')] = 101
    time_df.iloc[10, time_df.columns.get_loc('close')] = 101
    time_df.iloc[11, time_df.columns.get_loc('open')] = 101
    time_df.iloc[11, time_df.columns.get_loc('high')] = 101
    time_df.iloc[11, time_df.columns.get_loc('close')] = 101
    time_result = run_vwap_volume_reversion_backtest(
        time_df,
        vwap_window=5,
        z_window=2,
        rsi_period=3,
        stochrsi_period=3,
        volume_window=4,
        atr_period=3,
        z_threshold=0.5,
        rsi_long=45,
        stochrsi_long=0.8,
        volume_multiple=2.0,
        atr_target_multiple=10.0,
        atr_stop_multiple=10.0,
        max_hold_bars=2,
    )
    assert time_result.trades.iloc[0]['exit_reason'] == 'time_stop'
