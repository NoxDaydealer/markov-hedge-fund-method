from __future__ import annotations

import json
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


def adapter_kwargs() -> dict[str, object]:
    return {
        'vwap_window': 5,
        'z_window': 2,
        'rsi_period': 3,
        'stochrsi_period': 3,
        'volume_window': 4,
        'atr_period': 3,
        'z_threshold': 0.5,
        'rsi_long': 45,
        'stochrsi_long': 0.8,
        'volume_multiple': 2.0,
        'enable_shorts': False,
    }


def test_adapter_exports_research_only_next_bar_signal_with_markov_default_off(monkeypatch):
    from trading_hub.strategies.vwap_volume_rsi_reversion import VWAPVolumeRSIReversionAdapter

    def fail_network(*args, **kwargs):
        raise AssertionError('research adapter must not open network connections')

    monkeypatch.setattr(socket, 'create_connection', fail_network)
    monkeypatch.setattr(socket.socket, 'connect', fail_network)

    adapter = VWAPVolumeRSIReversionAdapter(**adapter_kwargs())
    signals = adapter.generate_signals(fixture_1m_ohlcv())

    assert adapter.markov_gate == 'off'
    assert 'markov_trade_allowed' in signals.columns
    assert 'markov_reason' in signals.columns
    assert signals['markov_trade_allowed'].all()
    assert signals['raw_signal'].iloc[8] == 1
    assert signals['execution_signal'].iloc[8] == 0
    assert signals['execution_signal'].iloc[9] == 1
    assert signals['execution_price'].iloc[9] == pytest.approx(100.0)
    assert signals['reason'].iloc[8] == 'long_vwap_volume_rsi_reclaim'


def test_adapter_loads_confirmed_bybit_collector_jsonl_and_filters_symbol(tmp_path):
    from trading_hub.strategies.vwap_volume_rsi_reversion import VWAPVolumeRSIReversionAdapter

    path = tmp_path / 'BTCUSDT.jsonl'
    with path.open('w', encoding='utf-8') as handle:
        for timestamp_ms, row in zip(pd.date_range('2024-01-01', periods=18, freq='min').view('int64') // 1_000_000, fixture_1m_ohlcv().reset_index(drop=True).to_dict('records')):
            record = {'symbol': 'BTCUSDT', 'start_ms': int(timestamp_ms), 'interval': '1', 'confirmed': True, 'turnover': 1_000_000.0, **row}
            handle.write(json.dumps(record) + '\n')
        handle.write(json.dumps({'symbol': 'ETHUSDT', 'start_ms': 1704068280000, 'interval': '1', 'confirmed': True, 'open': 1, 'high': 1, 'low': 1, 'close': 1, 'volume': 1}) + '\n')
        handle.write(json.dumps({'symbol': 'BTCUSDT', 'start_ms': 1704068340000, 'interval': '1', 'confirmed': False, 'open': 2, 'high': 2, 'low': 2, 'close': 2, 'volume': 2}) + '\n')

    frame = VWAPVolumeRSIReversionAdapter.load_bybit_ohlcv_jsonl(path, symbol='BTCUSDT')

    assert len(frame) == 18
    assert frame.index[0] == pd.Timestamp('2024-01-01 00:00:00')
    assert set(frame.columns) >= {'open', 'high', 'low', 'close', 'volume', 'symbol', 'start_ms'}
    assert frame['symbol'].eq('BTCUSDT').all()


def test_backtest_applies_explicit_costs_and_paper_only_short_default():
    from trading_hub.vwap_volume_rsi_reversion_backtest import run_vwap_volume_rsi_reversion_backtest

    result = run_vwap_volume_rsi_reversion_backtest(
        fixture_1m_ohlcv(),
        **adapter_kwargs(),
        atr_target_multiple=10.0,
        atr_stop_multiple=1.0,
        max_hold_bars=6,
        fee_bps=4.0,
        spread_bps=5.0,
        slippage_bps=3.0,
    )

    assert result.strategy == 'vwap_volume_rsi_reversion_research'
    assert result.metrics['trades'] == 1
    assert result.metrics['short_trades'] == 0
    trade = result.trades.iloc[0]
    assert trade['entry_time'] == pd.Timestamp('2024-01-01 00:09:00')
    assert trade['side'] == 1
    assert trade['cost_return'] == pytest.approx(0.0012)
    assert trade['gross_return'] > trade['net_return']


def test_cli_accepts_bybit_jsonl_and_writes_research_report(tmp_path, capsys):
    from trading_hub.vwap_volume_rsi_reversion_backtest import main

    jsonl = tmp_path / 'BTCUSDT.jsonl'
    with jsonl.open('w', encoding='utf-8') as handle:
        for timestamp_ms, row in zip(pd.date_range('2024-01-01', periods=18, freq='min').view('int64') // 1_000_000, fixture_1m_ohlcv().reset_index(drop=True).to_dict('records')):
            handle.write(json.dumps({'symbol': 'BTCUSDT', 'start_ms': int(timestamp_ms), 'interval': '1', 'confirmed': True, 'turnover': 1.0, **row}) + '\n')
    output = tmp_path / 'report.json'

    exit_code = main([
        '--bybit-jsonl', str(jsonl),
        '--symbol', 'BTCUSDT',
        '--output-json', str(output),
        '--vwap-window', '5',
        '--z-window', '2',
        '--rsi-period', '3',
        '--stochrsi-period', '3',
        '--volume-window', '4',
        '--atr-period', '3',
        '--z-threshold', '0.5',
        '--rsi-long', '45',
        '--stochrsi-long', '0.8',
        '--volume-multiple', '2.0',
        '--atr-target-multiple', '10',
        '--fee-bps', '4',
        '--spread-bps', '5',
        '--slippage-bps', '3',
    ])

    printed = capsys.readouterr().out
    report = json.loads(output.read_text(encoding='utf-8'))
    assert exit_code == 0
    assert 'daily paper reports: disabled' in printed
    assert report['strategy'] == 'vwap_volume_rsi_reversion_research'
    assert report['research_only'] is True
    assert report['paper_reports_enabled'] is False
    assert report['config']['markov_gate'] == 'off'
