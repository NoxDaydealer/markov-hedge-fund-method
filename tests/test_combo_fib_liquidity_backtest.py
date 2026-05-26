from __future__ import annotations

import json
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


def test_backtest_uses_execution_signal_for_next_open_to_next_open_returns():
    from trading_hub.backtest_report import run_combo_fib_liquidity_backtest

    result = run_combo_fib_liquidity_backtest(
        fixture_ohlcv(),
        lookback=6,
        atr_period=3,
        markov_signal=0.0,
        periods_per_year=252,
    )

    assert result.metrics['trades'] == 1
    assert result.metrics['wins'] == 1
    assert result.metrics['win_rate'] == pytest.approx(1.0)
    assert result.metrics['total_return'] == pytest.approx((108 - 104) / 104)
    assert result.trades.loc[0, 'entry_time'] == pd.Timestamp('2024-01-11')
    assert result.trades.loc[0, 'exit_time'] == pd.Timestamp('2024-01-12')
    assert result.trades.loc[0, 'side'] == 1
    assert result.trades.loc[0, 'entry_price'] == pytest.approx(104.0)
    assert result.trades.loc[0, 'exit_price'] == pytest.approx(108.0)
    assert result.trades.loc[0, 'return'] == pytest.approx((108 - 104) / 104)
    assert result.trades.loc[0, 'reason'] == 'long_liquidity_sweep_fib_reclaim'


def test_backtest_drops_last_execution_when_next_bar_return_is_unavailable():
    from trading_hub.backtest_report import run_combo_fib_liquidity_backtest

    df = fixture_ohlcv().iloc[:11]
    result = run_combo_fib_liquidity_backtest(df, lookback=6, atr_period=3, markov_signal=0.0)

    assert result.metrics['trades'] == 0
    assert result.metrics['win_rate'] == 0.0
    assert result.trades.empty


def test_report_runner_reads_local_csv_and_writes_json_without_network(tmp_path: Path, monkeypatch):
    from trading_hub.backtest_report import main

    def fail_network(*args, **kwargs):
        raise AssertionError('network calls are forbidden for local CSV backtests')

    monkeypatch.setattr(socket, 'create_connection', fail_network)
    monkeypatch.setattr(socket.socket, 'connect', fail_network)
    csv_path = tmp_path / 'ohlcv.csv'
    output_path = tmp_path / 'report.json'
    fixture_ohlcv().reset_index(names='date').to_csv(csv_path, index=False)

    exit_code = main(
        [
            '--csv',
            str(csv_path),
            '--output-json',
            str(output_path),
            '--lookback',
            '6',
            '--atr-period',
            '3',
            '--markov-signal',
            '0',
        ]
    )

    assert exit_code == 0
    report = json.loads(output_path.read_text(encoding='utf-8'))
    assert report['strategy'] == 'combo_fib_liquidity'
    assert report['data_source'] == str(csv_path)
    assert report['metrics']['trades'] == 1
    assert report['metrics']['total_return'] == pytest.approx((108 - 104) / 104)


def test_yfinance_fetch_requires_explicit_ticker_option(monkeypatch):
    from trading_hub.backtest_report import main

    called = False

    def fake_download(symbol, *, period, interval, auto_adjust, progress):
        nonlocal called
        called = True
        assert symbol == 'SPY'
        assert period == '1mo'
        assert interval == '1d'
        assert auto_adjust is False
        assert progress is False
        return fixture_ohlcv().rename(columns=str.title)

    class FakeYfinance:
        download = staticmethod(fake_download)

    monkeypatch.setitem(__import__('sys').modules, 'yfinance', FakeYfinance)

    exit_code = main(['--ticker', 'SPY', '--period', '1mo', '--lookback', '6', '--atr-period', '3'])

    assert exit_code == 0
    assert called is True
