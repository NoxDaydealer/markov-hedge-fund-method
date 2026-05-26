from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path('/root/.hermes/scripts/trading_hub_daily_markov_report.py')


def load_report_module():
    spec = importlib.util.spec_from_file_location('trading_hub_daily_markov_report', SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_config(path: Path, assets: list[dict]) -> None:
    import yaml

    path.write_text(yaml.safe_dump({'version': 1, 'assets': assets}, sort_keys=False), encoding='utf-8')


def asset(symbol: str, *, enabled: bool = True, min_history_rows: int = 252) -> dict:
    return {
        'symbol': symbol,
        'display_name': symbol,
        'asset_class': 'crypto' if symbol.endswith('-USD') else 'equity_index_etf',
        'data_source': 'yfinance',
        'enabled': enabled,
        'min_history_rows': min_history_rows,
        'report_group': 'core',
        'notes': 'test asset',
    }


def test_default_config_enabled_universe_matches_existing_tickers():
    report = load_report_module()

    entries = report.load_universe_config()

    assert [entry.symbol for entry in entries] == ['BTC-USD', 'ETH-USD', 'SPY', 'QQQ']


def test_disabled_assets_are_skipped(tmp_path: Path):
    report = load_report_module()
    config_path = tmp_path / 'universe.yaml'
    write_config(config_path, [asset('BTC-USD'), asset('DISABLED', enabled=False), asset('SPY')])

    entries = report.load_universe_config(config_path)

    assert [entry.symbol for entry in entries] == ['BTC-USD', 'SPY']


def test_config_entries_include_required_metadata(tmp_path: Path):
    report = load_report_module()
    config_path = tmp_path / 'universe.yaml'
    write_config(config_path, [asset('QQQ', min_history_rows=504)])

    entry = report.load_universe_config(config_path)[0]

    assert entry.symbol == 'QQQ'
    assert entry.display_name == 'QQQ'
    assert entry.asset_class == 'equity_index_etf'
    assert entry.data_source == 'yfinance'
    assert entry.enabled is True
    assert entry.min_history_rows == 504
    assert entry.report_group == 'core'
    assert entry.notes == 'test asset'


@pytest.mark.parametrize(
    ('contents', 'expected'),
    [
        ('not: [valid', 'Could not read asset universe config'),
        ('version: 1\nassets:\n  - symbol: ONLY\n', 'missing required field'),
        ('version: 1\nassets: []\n', 'No enabled assets'),
    ],
)
def test_malformed_config_raises_readable_error(tmp_path: Path, contents: str, expected: str):
    report = load_report_module()
    config_path = tmp_path / 'bad.yaml'
    config_path.write_text(contents, encoding='utf-8')

    with pytest.raises(report.UniverseConfigError) as excinfo:
        report.load_universe_config(config_path)

    assert expected in str(excinfo.value)
    assert 'Traceback' not in str(excinfo.value)


def test_main_prints_readable_config_error_without_traceback(tmp_path: Path, capsys, monkeypatch):
    report = load_report_module()
    missing_path = tmp_path / 'missing.yaml'
    monkeypatch.setattr(report, 'UNIVERSE_CONFIG', missing_path)

    report.main()

    captured = capsys.readouterr()
    assert 'Asset universe config error:' in captured.out
    assert 'Traceback' not in captured.out
    assert captured.err == ''
