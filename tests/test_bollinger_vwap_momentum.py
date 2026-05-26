from __future__ import annotations

import json
import socket
from pathlib import Path

import pandas as pd
import pytest


def fixture_intraday_ohlcv() -> pd.DataFrame:
    index = pd.date_range('2024-01-01 09:30', periods=18, freq='min')
    return pd.DataFrame(
        {
            'open': [100.00, 100.05, 99.95, 100.02, 99.98, 100.00, 100.04, 99.96, 100.01, 100.03, 100.00, 100.02, 100.01, 103.20, 104.40, 105.20, 105.00, 100.20],
            'high': [100.15, 100.12, 100.08, 100.10, 100.06, 100.08, 100.12, 100.05, 100.09, 100.08, 100.07, 100.08, 100.06, 104.20, 105.60, 106.00, 105.30, 100.50],
            'low': [99.90, 99.95, 99.88, 99.94, 99.90, 99.92, 99.96, 99.88, 99.95, 99.98, 99.94, 99.96, 99.95, 103.00, 104.00, 104.80, 100.70, 99.80],
            'close': [100.05, 99.98, 100.02, 100.00, 100.01, 100.03, 99.99, 100.02, 100.04, 100.01, 100.03, 100.04, 100.02, 104.00, 105.30, 105.10, 101.00, 100.00],
            'volume': [1000, 980, 1010, 990, 1005, 995, 1020, 1000, 990, 1010, 1200, 1300, 1450, 3600, 2800, 2400, 2600, 3000],
        },
        index=index,
    )


def adapter_kwargs() -> dict[str, float | int]:
    return {
        'bb_period': 5,
        'bandwidth_percentile_window': 6,
        'bandwidth_percentile_threshold': 0.60,
        'volume_window': 5,
        'volume_multiplier': 1.8,
        'rsi_period': 3,
        'rsi_long_threshold': 55,
        'macd_fast': 3,
        'macd_slow': 6,
        'macd_signal': 2,
        'atr_period': 3,
        'atr_trailing_multiple': 1.2,
        'max_holding_bars': 4,
    }


def test_adapter_emits_next_bar_signal_after_squeeze_breakout_vwap_volume_and_momentum_confirm():
    from trading_hub.strategies.bollinger_vwap_momentum import BollingerVwapMomentumAdapter

    signals = BollingerVwapMomentumAdapter(**adapter_kwargs()).generate_signals(fixture_intraday_ohlcv())

    assert list(signals.columns) == [
        'raw_signal',
        'signal',
        'execution_signal',
        'execution_price',
        'vwap',
        'bb_upper',
        'bb_lower',
        'bb_bandwidth_percentile',
        'rsi',
        'macd',
        'macd_signal',
        'atr',
        'reason',
    ]
    assert signals['raw_signal'].iloc[13] == 1
    assert signals['signal'].iloc[13] == 1
    assert signals['execution_signal'].iloc[13] == 0
    assert signals['execution_signal'].iloc[14] == 1
    assert signals['execution_price'].iloc[14] == pytest.approx(104.40)
    assert signals['reason'].iloc[13] == 'long_bollinger_vwap_momentum_breakout'
    assert signals['bb_bandwidth_percentile'].iloc[12] <= 0.60
    assert signals['vwap'].iloc[13] < fixture_intraday_ohlcv()['close'].iloc[13]


def test_csv_input_matches_dataframe_and_adapter_makes_no_network_calls(tmp_path: Path, monkeypatch):
    from trading_hub.strategies.bollinger_vwap_momentum import BollingerVwapMomentumAdapter

    def fail_network(*args, **kwargs):
        raise AssertionError('network calls are forbidden in paper strategy adapter')

    monkeypatch.setattr(socket, 'create_connection', fail_network)
    monkeypatch.setattr(socket.socket, 'connect', fail_network)
    df = fixture_intraday_ohlcv()
    csv_path = tmp_path / 'intraday.csv'
    df.reset_index(names='timestamp').to_csv(csv_path, index=False)

    adapter = BollingerVwapMomentumAdapter(**adapter_kwargs())
    from_df = adapter.generate_signals(df)
    from_csv = adapter.generate_signals(csv_path)

    pd.testing.assert_frame_equal(from_csv, from_df)


def test_no_future_bar_usage_prior_rows_unchanged_when_future_changes():
    from trading_hub.strategies.bollinger_vwap_momentum import BollingerVwapMomentumAdapter

    base = fixture_intraday_ohlcv()
    changed_future = base.copy()
    changed_future.iloc[16, changed_future.columns.get_loc('high')] = 999
    changed_future.iloc[16, changed_future.columns.get_loc('low')] = 1
    changed_future.iloc[16, changed_future.columns.get_loc('close')] = 500

    adapter = BollingerVwapMomentumAdapter(**adapter_kwargs())
    base_signals = adapter.generate_signals(base)
    changed_signals = adapter.generate_signals(changed_future)

    pd.testing.assert_frame_equal(base_signals.iloc[:16], changed_signals.iloc[:16])


def test_backtest_uses_atr_trailing_exit_and_applies_cost_hooks():
    from trading_hub.backtest_report import run_bollinger_vwap_momentum_backtest

    result = run_bollinger_vwap_momentum_backtest(
        fixture_intraday_ohlcv(),
        periods_per_year=252 * 390,
        fee_bps=2.0,
        spread_bps=1.0,
        slippage_bps=1.0,
        **adapter_kwargs(),
    )

    assert result.strategy == 'bollinger_vwap_momentum'
    assert result.metrics['trades'] == 1
    assert result.trades.loc[0, 'entry_time'] == pd.Timestamp('2024-01-01 09:44')
    assert result.trades.loc[0, 'exit_time'] == pd.Timestamp('2024-01-01 09:46')
    assert result.trades.loc[0, 'side'] == 1
    assert result.trades.loc[0, 'entry_price'] == pytest.approx(104.40)
    assert result.trades.loc[0, 'exit_reason'] == 'atr_trailing_stop'
    gross_return = (result.trades.loc[0, 'exit_price'] - 104.40) / 104.40
    assert result.trades.loc[0, 'gross_return'] == pytest.approx(gross_return)
    assert result.trades.loc[0, 'cost_return'] == pytest.approx(0.0008)
    assert result.trades.loc[0, 'return'] == pytest.approx(gross_return - 0.0008)
    assert result.metrics['total_return'] == pytest.approx(result.trades.loc[0, 'return'])


def test_report_runner_reads_local_csv_for_bollinger_vwap_json_without_network(tmp_path: Path, monkeypatch):
    from trading_hub.backtest_report import main

    def fail_network(*args, **kwargs):
        raise AssertionError('network calls are forbidden for local CSV backtests')

    monkeypatch.setattr(socket, 'create_connection', fail_network)
    monkeypatch.setattr(socket.socket, 'connect', fail_network)
    csv_path = tmp_path / 'intraday.csv'
    output_path = tmp_path / 'report.json'
    fixture_intraday_ohlcv().reset_index(names='timestamp').to_csv(csv_path, index=False)

    exit_code = main(
        [
            '--strategy',
            'bollinger_vwap_momentum',
            '--csv',
            str(csv_path),
            '--output-json',
            str(output_path),
            '--bb-period',
            '5',
            '--bandwidth-percentile-window',
            '6',
            '--bandwidth-percentile-threshold',
            '0.60',
            '--volume-window',
            '5',
            '--volume-multiplier',
            '1.8',
            '--rsi-period',
            '3',
            '--macd-fast',
            '3',
            '--macd-slow',
            '6',
            '--macd-signal',
            '2',
            '--atr-period',
            '3',
            '--atr-trailing-multiple',
            '1.2',
            '--max-holding-bars',
            '4',
            '--fee-bps',
            '2',
            '--spread-bps',
            '1',
            '--slippage-bps',
            '1',
        ]
    )

    assert exit_code == 0
    report = json.loads(output_path.read_text(encoding='utf-8'))
    assert report['strategy'] == 'bollinger_vwap_momentum'
    assert report['data_source'] == str(csv_path)
    assert report['metrics']['trades'] == 1
