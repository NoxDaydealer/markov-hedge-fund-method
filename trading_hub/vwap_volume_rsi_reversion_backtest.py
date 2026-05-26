from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from trading_hub.strategies.vwap_volume_rsi_reversion import VWAPVolumeRSIReversionAdapter
from trading_hub.vwap_volume_reversion_backtest import (
    _compute_metrics,
    _format_summary,
    _frame_to_json_records,
    _round_trip_cost,
    _simulate_trades,
)


@dataclass(frozen=True)
class VWAPVolumeRSIReversionBacktestResult:
    strategy: str
    data_source: str
    metrics: dict[str, float | int]
    signals: pd.DataFrame
    trades: pd.DataFrame
    equity_curve: pd.Series
    config: dict[str, Any]
    research_only: bool = True
    paper_reports_enabled: bool = False
    sprint_verdict: str = 'partial_no_go_after_cost_holdout; daily paper reports disabled until walk-forward validation passes'

    def to_dict(self) -> dict[str, Any]:
        return {
            'strategy': self.strategy,
            'data_source': self.data_source,
            'research_only': self.research_only,
            'paper_reports_enabled': self.paper_reports_enabled,
            'sprint_verdict': self.sprint_verdict,
            'config': self.config,
            'metrics': self.metrics,
            'trades': _frame_to_json_records(self.trades),
        }


def run_vwap_volume_rsi_reversion_backtest(
    data: pd.DataFrame | str | Path,
    *,
    data_source: str | None = None,
    bybit_jsonl: bool = False,
    symbol: str | None = None,
    periods_per_year: int = 365 * 24 * 60,
    fee_bps: float = 4.0,
    spread_bps: float = 5.0,
    slippage_bps: float = 3.0,
    max_hold_bars: int = 20,
    **adapter_kwargs: Any,
) -> VWAPVolumeRSIReversionBacktestResult:
    """Run research-only VWAP/Volume/RSI reversion backtest.

    Entries consume the adapter's no-lookahead next-bar execution signal. Costs
    are explicit bps hooks and default to the sprint's conservative 12 bps
    completed-trade assumption split across fee/spread/slippage placeholders.
    """

    if max_hold_bars < 1:
        raise ValueError('max_hold_bars must be at least 1')
    adapter = VWAPVolumeRSIReversionAdapter(**adapter_kwargs)
    frame = adapter.load_bybit_ohlcv_jsonl(data, symbol=symbol) if bybit_jsonl else adapter._load_ohlcv(data)
    cost_return = _round_trip_cost(fee_bps=fee_bps, spread_bps=spread_bps, slippage_bps=slippage_bps)
    signals = adapter.generate_signals(frame)
    gross_returns, net_returns, trades = _simulate_trades(
        frame,
        signals,
        max_hold_bars=max_hold_bars,
        cost_return=cost_return,
    )
    equity_curve = (1.0 + net_returns).cumprod()
    metrics = _compute_metrics(net_returns, gross_returns, trades, signals, periods_per_year=periods_per_year)
    config = asdict(adapter)
    config.update(
        {
            'fee_bps': fee_bps,
            'spread_bps': spread_bps,
            'slippage_bps': slippage_bps,
            'round_trip_cost_return': cost_return,
            'max_hold_bars': max_hold_bars,
            'symbol': symbol,
        }
    )
    return VWAPVolumeRSIReversionBacktestResult(
        strategy='vwap_volume_rsi_reversion_research',
        data_source=data_source if data_source is not None else _describe_data_source(data, bybit_jsonl=bybit_jsonl),
        metrics=metrics,
        signals=signals,
        trades=trades,
        equity_curve=equity_curve,
        config=config,
    )


def load_csv(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if bool(args.csv) == bool(args.bybit_jsonl):
        parser.error('provide exactly one of --csv or --bybit-jsonl')

    source = args.bybit_jsonl or args.csv
    result = run_vwap_volume_rsi_reversion_backtest(
        source,
        data_source=str(source),
        bybit_jsonl=bool(args.bybit_jsonl),
        symbol=args.symbol,
        periods_per_year=args.periods_per_year,
        fee_bps=args.fee_bps,
        spread_bps=args.spread_bps,
        slippage_bps=args.slippage_bps,
        max_hold_bars=args.max_hold_bars,
        vwap_window=args.vwap_window,
        z_window=args.z_window,
        rsi_period=args.rsi_period,
        stochrsi_period=args.stochrsi_period,
        volume_window=args.volume_window,
        atr_period=args.atr_period,
        z_threshold=args.z_threshold,
        rsi_long=args.rsi_long,
        rsi_short=args.rsi_short,
        stochrsi_long=args.stochrsi_long,
        stochrsi_short=args.stochrsi_short,
        volume_multiple=args.volume_multiple,
        enable_shorts=args.enable_shorts,
        atr_stop_multiple=args.atr_stop_multiple,
        atr_target_multiple=args.atr_target_multiple,
        markov_gate=args.markov_gate,
        markov_lookback=args.markov_lookback,
        markov_min_train=args.markov_min_train,
    )
    report = result.to_dict()
    if args.output_json:
        Path(args.output_json).write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(_format_summary(report))
    print('Research-only: true; real orders: disabled; daily paper reports: disabled until walk-forward after-cost validation passes')
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Research-only Bybit VWAP+Volume+RSI reversion backtest')
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--csv', help='Local 1m OHLCV CSV path; no network calls are made')
    source.add_argument('--bybit-jsonl', help='Normalized Bybit collector OHLCV JSONL path')
    parser.add_argument('--symbol', choices=['BTCUSDT', 'ETHUSDT'], help='Filter normalized Bybit JSONL to one linear symbol')
    parser.add_argument('--vwap-window', type=int, default=240)
    parser.add_argument('--z-window', type=int, default=240)
    parser.add_argument('--rsi-period', type=int, default=14)
    parser.add_argument('--stochrsi-period', type=int, default=14)
    parser.add_argument('--volume-window', type=int, default=60)
    parser.add_argument('--atr-period', type=int, default=14)
    parser.add_argument('--z-threshold', type=float, default=1.5)
    parser.add_argument('--rsi-long', type=float, default=35.0)
    parser.add_argument('--rsi-short', type=float, default=65.0)
    parser.add_argument('--stochrsi-long', type=float, default=0.20)
    parser.add_argument('--stochrsi-short', type=float, default=0.80)
    parser.add_argument('--volume-multiple', type=float, default=1.2)
    parser.add_argument('--enable-shorts', action='store_true', help='Allow paper-only short research signals')
    parser.add_argument('--atr-stop-multiple', type=float, default=0.8)
    parser.add_argument('--atr-target-multiple', type=float, default=1.5)
    parser.add_argument('--max-hold-bars', type=int, default=20)
    parser.add_argument('--markov-gate', choices=['off', 'neutral_only', 'contrarian_ok'], default='off')
    parser.add_argument('--markov-lookback', type=int, default=20)
    parser.add_argument('--markov-min-train', type=int, default=20)
    parser.add_argument('--fee-bps', type=float, default=4.0)
    parser.add_argument('--spread-bps', type=float, default=5.0)
    parser.add_argument('--slippage-bps', type=float, default=3.0)
    parser.add_argument('--periods-per-year', type=int, default=365 * 24 * 60)
    parser.add_argument('--output-json', help='Optional path to write machine-readable research report JSON')
    return parser


def _describe_data_source(data: pd.DataFrame | str | Path, *, bybit_jsonl: bool) -> str:
    if isinstance(data, (str, Path)):
        prefix = 'bybit-jsonl:' if bybit_jsonl else ''
        return f'{prefix}{data}'
    return 'dataframe'


if __name__ == '__main__':  # pragma: no cover
    raise SystemExit(main())
