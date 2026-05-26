"""Unified strategy comparison report: all adapters evaluated on the same OHLCV dataset.

CLI:
    python -m trading_hub.combo_comparison_report --csv data.csv --date 2026-05-25

Python API:
    from trading_hub.combo_comparison_report import run_combo_comparison
    results = run_combo_comparison(ohlcv, date_str)
"""
from __future__ import annotations

import argparse
import warnings
from pathlib import Path
from typing import Any

import pandas as pd

from trading_hub.combo_signal import RegimeGatedComboConfig, build_regime_gated_combo_signal
from trading_hub.go_no_go_gate import add_gate_column_to_results
from trading_hub.hft_evaluator import (
    EvaluationResult,
    build_baseline_signals,
    evaluate_intraday_strategy,
)
from trading_hub.strategies.bollinger_vwap_momentum import BollingerVwapMomentumAdapter
from trading_hub.strategies.combo_fib_liquidity import ComboFibLiquidityAdapter
from trading_hub.strategies.intraday_markov_gate import IntradayMarkovRegimeGate
from trading_hub.strategies.vwap_volume_reversion import VWAPVolumeReversionAdapter
from trading_hub.strategies.vwap_volume_rsi_reversion import VWAPVolumeRSIReversionAdapter

CSV_COLUMNS = [
    'strategy',
    'net_pnl',
    'max_drawdown',
    'fee_to_gross_profit',
    'trades',
    'beats_random',
    'sharpe_ratio',
    'win_rate',
    'gate',
]

# Internal baseline key → display name in CSV/MD
_BASELINE_NAME_MAP = {
    'no_trade': 'no_trade',
    'buy_hold': 'buy_hold',
    'random_same_frequency': 'random_same_freq',
    'naive_vwap_reversion': 'naive_vwap',
}


def _safe_signal(adapter: Any, data: pd.DataFrame, name: str) -> pd.Series | None:
    try:
        signals = adapter.generate_signals(data)
        return signals['signal']
    except Exception as exc:
        warnings.warn(f'[combo_comparison] {name} signal generation failed: {exc}')
        return None


def _build_strategy_signals(ohlcv: pd.DataFrame) -> dict[str, pd.Series]:
    signals: dict[str, pd.Series] = {}

    # 1. VWAPVolumeReversionAdapter (baseline, markov=off)
    sig = _safe_signal(VWAPVolumeReversionAdapter(), ohlcv, 'vwap_reversion_baseline')
    if sig is not None:
        signals['vwap_reversion_baseline'] = sig

    # 2. VWAPVolumeRSIReversionAdapter (markov=neutral_only)
    sig = _safe_signal(VWAPVolumeRSIReversionAdapter(markov_gate='neutral_only'), ohlcv, 'vwap_rsi_markov_neutral')
    if sig is not None:
        signals['vwap_rsi_markov_neutral'] = sig

    # 3. VWAPVolumeRSIReversionAdapter (markov=contrarian_ok)
    sig = _safe_signal(VWAPVolumeRSIReversionAdapter(markov_gate='contrarian_ok'), ohlcv, 'vwap_rsi_markov_contrarian')
    if sig is not None:
        signals['vwap_rsi_markov_contrarian'] = sig

    # 4. BollingerVwapMomentumAdapter (shorts=off)
    sig = _safe_signal(BollingerVwapMomentumAdapter(enable_shorts=False), ohlcv, 'bollinger_vwap_no_shorts')
    if sig is not None:
        signals['bollinger_vwap_no_shorts'] = sig

    # 5. BollingerVwapMomentumAdapter (shorts=on)
    sig = _safe_signal(BollingerVwapMomentumAdapter(enable_shorts=True), ohlcv, 'bollinger_vwap_shorts')
    if sig is not None:
        signals['bollinger_vwap_shorts'] = sig

    # 6. ComboFibLiquidityAdapter (daily, zur Referenz)
    sig = _safe_signal(ComboFibLiquidityAdapter(), ohlcv, 'combo_fib_liquidity')
    if sig is not None:
        signals['combo_fib_liquidity'] = sig

    # 7. RegimeGatedCombo (markov selects reversion vs momentum)
    try:
        gate_output = IntradayMarkovRegimeGate().generate(ohlcv)
        rev_sig = _safe_signal(VWAPVolumeReversionAdapter(), ohlcv, 'regime_gated_combo/reversion')
        mom_sig = _safe_signal(BollingerVwapMomentumAdapter(enable_shorts=False), ohlcv, 'regime_gated_combo/momentum')
        if rev_sig is not None and mom_sig is not None:
            signals['regime_gated_combo'] = build_regime_gated_combo_signal(
                gate_output,
                rev_sig,
                mom_sig,
                RegimeGatedComboConfig(
                    mean_reversion_regime='mean_reversion',
                    momentum_regime='momentum',
                ),
            )
    except Exception as exc:
        warnings.warn(f'[combo_comparison] regime_gated_combo failed: {exc}')

    return signals


def _reference_signal(signals: dict[str, pd.Series], index: pd.Index) -> pd.Series:
    """Build a synthetic signal with the average active-bar count across strategies."""
    if not signals:
        return pd.Series(0, index=index, dtype=int)

    active_counts = [int((s.reindex(index).fillna(0) != 0).sum()) for s in signals.values()]
    avg_active = max(1, round(sum(active_counts) / len(active_counts)))

    synthetic = pd.Series(0, index=index, dtype=int)
    n = len(index)
    if n > 0 and avg_active > 0:
        step = max(1, n // avg_active)
        for pos in range(0, n, step):
            if int((synthetic != 0).sum()) >= avg_active:
                break
            synthetic.iloc[pos] = 1
    return synthetic


def _row(name: str, result: EvaluationResult, random_pnl: float) -> dict:
    m = result.metrics
    return {
        'strategy': name,
        'net_pnl': m['net_pnl'],
        'max_drawdown': m['max_drawdown'],
        'fee_to_gross_profit': m['fee_to_gross_profit'],
        'trades': m['trades'],
        'beats_random': m['net_pnl'] > random_pnl,
        'sharpe_ratio': m['sharpe'],
        'win_rate': m['win_rate'],
    }


def run_combo_comparison(ohlcv: pd.DataFrame, date_str: str) -> list[dict]:
    """Evaluate all strategy variants on *ohlcv* and return a list of metric dicts.

    Each dict corresponds to one row in the output CSV/MD and contains the keys
    defined in ``CSV_COLUMNS``.
    """
    strategy_signals = _build_strategy_signals(ohlcv)

    strategy_results: dict[str, EvaluationResult] = {}
    for name, signal in strategy_signals.items():
        try:
            strategy_results[name] = evaluate_intraday_strategy(ohlcv, signal, name=name)
        except Exception as exc:
            warnings.warn(f'[combo_comparison] {name} evaluation failed: {exc}')

    ref_signal = _reference_signal(strategy_signals, ohlcv.index)
    baseline_signals = build_baseline_signals(ohlcv, ref_signal)

    baseline_results: dict[str, EvaluationResult] = {}
    for bname, bsig in baseline_signals.items():
        try:
            baseline_results[bname] = evaluate_intraday_strategy(ohlcv, bsig, name=bname)
        except Exception as exc:
            warnings.warn(f'[combo_comparison] baseline {bname} evaluation failed: {exc}')

    random_pnl = (
        baseline_results['random_same_frequency'].metrics['net_pnl']
        if 'random_same_frequency' in baseline_results
        else 0.0
    )

    rows: list[dict] = []
    for name, result in strategy_results.items():
        rows.append(_row(name, result, random_pnl))

    for internal_name, display_name in _BASELINE_NAME_MAP.items():
        if internal_name not in baseline_results:
            continue
        r = _row(display_name, baseline_results[internal_name], random_pnl)
        if display_name == 'random_same_freq':
            r['beats_random'] = False
        rows.append(r)

    return add_gate_column_to_results(rows)


def _md_table(df: pd.DataFrame) -> str:
    headers = list(df.columns)
    col_data: list[list[str]] = []
    for h in headers:
        cells: list[str] = []
        for v in df[h]:
            if isinstance(v, float):
                cells.append(f'{v:.6f}')
            else:
                cells.append(str(v))
        col_data.append(cells)

    widths = [
        max(len(h), max((len(c) for c in col), default=0))
        for h, col in zip(headers, col_data)
    ]

    def row_str(cells: list[str]) -> str:
        return '| ' + ' | '.join(f'{c:<{w}}' for c, w in zip(cells, widths)) + ' |'

    sep = '| ' + ' | '.join('-' * w for w in widths) + ' |'
    lines = [row_str(headers), sep]
    for i in range(len(df)):
        lines.append(row_str([col_data[j][i] for j in range(len(headers))]))
    return '\n'.join(lines)


def write_reports(rows: list[dict], date_str: str, reports_dir: Path) -> tuple[Path, Path]:
    """Write CSV and Markdown reports; return (csv_path, md_path)."""
    reports_dir.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(rows, columns=CSV_COLUMNS)
    csv_path = reports_dir / f'combo_comparison_{date_str}.csv'
    md_path = reports_dir / f'combo_comparison_{date_str}.md'

    df.to_csv(csv_path, index=False)

    md_content = '\n'.join([
        f'# Combo Strategy Comparison — {date_str}',
        '',
        _md_table(df),
        '',
    ])
    md_path.write_text(md_content, encoding='utf-8')

    return csv_path, md_path


def _load_csv(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    for ts_col in ('timestamp', 'date', 'time'):
        if ts_col in df.columns:
            df[ts_col] = pd.to_datetime(df[ts_col])
            df = df.set_index(ts_col)
            break
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description='Unified combo strategy comparison report')
    parser.add_argument('--csv', required=True, help='Path to OHLCV CSV file')
    parser.add_argument('--date', required=True, help='Report date (YYYY-MM-DD)')
    parser.add_argument(
        '--reports-dir',
        default='research/reports',
        help='Output directory (default: research/reports)',
    )
    args = parser.parse_args()

    ohlcv = _load_csv(args.csv)
    rows = run_combo_comparison(ohlcv, args.date)

    reports_dir = Path(args.reports_dir)
    csv_path, md_path = write_reports(rows, args.date, reports_dir)

    df = pd.DataFrame(rows, columns=CSV_COLUMNS)
    print(df.to_string(index=False))
    print(f'\nCSV: {csv_path}')
    print(f'MD:  {md_path}')


if __name__ == '__main__':
    main()
