from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from trading_hub.strategies.vwap_volume_reversion import VWAPVolumeReversionAdapter


@dataclass(frozen=True)
class VWAPVolumeReversionBacktestResult:
    strategy: str
    data_source: str
    metrics: dict[str, float | int]
    signals: pd.DataFrame
    trades: pd.DataFrame
    equity_curve: pd.Series

    def to_dict(self) -> dict[str, Any]:
        return {
            'strategy': self.strategy,
            'data_source': self.data_source,
            'metrics': self.metrics,
            'trades': _frame_to_json_records(self.trades),
        }


def run_vwap_volume_reversion_backtest(
    data: pd.DataFrame | str | Path,
    *,
    data_source: str | None = None,
    periods_per_year: int = 365 * 24 * 60,
    fee_bps: float = 0.0,
    spread_bps: float = 0.0,
    slippage_bps: float = 0.0,
    max_hold_bars: int = 20,
    **adapter_kwargs: Any,
) -> VWAPVolumeReversionBacktestResult:
    """Run pure local VWAP-volume-reversion backtest with cost hooks.

    Entries use the adapter's next-bar ``execution_signal`` and fill at the
    execution bar open. Exits scan subsequent bars for the first VWAP/ATR target,
    ATR/local-extreme stop, or configured time stop. Returns are booked on the
    exit bar only, with round-trip costs deducted from each completed trade.
    """

    if max_hold_bars < 1:
        raise ValueError('max_hold_bars must be at least 1')
    cost_return = _round_trip_cost(fee_bps=fee_bps, spread_bps=spread_bps, slippage_bps=slippage_bps)
    adapter = VWAPVolumeReversionAdapter(**adapter_kwargs)
    frame = adapter._load_ohlcv(data)
    signals = adapter.generate_signals(frame)
    gross_returns, net_returns, trades = _simulate_trades(
        frame,
        signals,
        max_hold_bars=max_hold_bars,
        cost_return=cost_return,
    )
    equity_curve = (1.0 + net_returns).cumprod()
    metrics = _compute_metrics(net_returns, gross_returns, trades, signals, periods_per_year=periods_per_year)
    return VWAPVolumeReversionBacktestResult(
        strategy='vwap_volume_reversion_v0',
        data_source=data_source if data_source is not None else _describe_data_source(data),
        metrics=metrics,
        signals=signals,
        trades=trades,
        equity_curve=equity_curve,
    )


def load_csv(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    result = run_vwap_volume_reversion_backtest(
        load_csv(args.csv),
        data_source=args.csv,
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
    )
    report = result.to_dict()
    if args.output_json:
        Path(args.output_json).write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(_format_summary(report))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Paper-only VWAP volume reversion v0 backtest')
    parser.add_argument('--csv', required=True, help='Local 1m/5m OHLCV CSV path; no network calls are made')
    parser.add_argument('--vwap-window', type=int, default=240)
    parser.add_argument('--z-window', type=int, default=240)
    parser.add_argument('--rsi-period', type=int, default=14)
    parser.add_argument('--stochrsi-period', type=int, default=14)
    parser.add_argument('--volume-window', type=int, default=60)
    parser.add_argument('--atr-period', type=int, default=14)
    parser.add_argument('--z-threshold', type=float, default=1.0)
    parser.add_argument('--rsi-long', type=float, default=30.0)
    parser.add_argument('--rsi-short', type=float, default=70.0)
    parser.add_argument('--stochrsi-long', type=float, default=0.20)
    parser.add_argument('--stochrsi-short', type=float, default=0.80)
    parser.add_argument('--volume-multiple', type=float, default=1.5)
    parser.add_argument('--enable-shorts', action='store_true')
    parser.add_argument('--atr-stop-multiple', type=float, default=1.0)
    parser.add_argument('--atr-target-multiple', type=float, default=1.5)
    parser.add_argument('--max-hold-bars', type=int, default=20)
    parser.add_argument('--fee-bps', type=float, default=0.0)
    parser.add_argument('--spread-bps', type=float, default=0.0)
    parser.add_argument('--slippage-bps', type=float, default=0.0)
    parser.add_argument('--periods-per-year', type=int, default=365 * 24 * 60)
    parser.add_argument('--output-json', help='Optional path to write machine-readable report JSON')
    return parser


def _simulate_trades(
    frame: pd.DataFrame,
    signals: pd.DataFrame,
    *,
    max_hold_bars: int,
    cost_return: float,
) -> tuple[pd.Series, pd.Series, pd.DataFrame]:
    gross_returns = pd.Series(0.0, index=frame.index)
    net_returns = pd.Series(0.0, index=frame.index)
    records: list[dict[str, Any]] = []
    in_trade_until = -1
    idx = list(frame.index)
    for i, ts in enumerate(idx[:-1]):
        if i <= in_trade_until:
            continue
        side = int(signals['execution_signal'].iloc[i])
        if side == 0 or not np.isfinite(float(signals['atr'].iloc[i])):
            continue
        entry_price = float(frame['open'].iloc[i])
        target = float(signals['target_price'].iloc[i]) if pd.notna(signals['target_price'].iloc[i]) else np.nan
        stop = float(signals['stop_price'].iloc[i]) if pd.notna(signals['stop_price'].iloc[i]) else np.nan
        exit_i = min(i + max_hold_bars, len(frame) - 1)
        exit_price = float(frame['close'].iloc[exit_i])
        exit_reason = 'time_stop'
        for j in range(i + 1, min(i + max_hold_bars, len(frame) - 1) + 1):
            high = float(frame['high'].iloc[j])
            low = float(frame['low'].iloc[j])
            close = float(frame['close'].iloc[j])
            if side == 1:
                if np.isfinite(stop) and low <= stop:
                    exit_i, exit_price, exit_reason = j, stop, 'atr_or_local_extreme_stop'
                    break
                if np.isfinite(target) and high >= target:
                    exit_i, exit_price, exit_reason = j, target, 'vwap_target'
                    break
            else:
                if np.isfinite(stop) and high >= stop:
                    exit_i, exit_price, exit_reason = j, stop, 'atr_or_local_extreme_stop'
                    break
                if np.isfinite(target) and low <= target:
                    exit_i, exit_price, exit_reason = j, target, 'vwap_target'
                    break
            exit_i, exit_price = j, close
        gross = side * (exit_price / entry_price - 1.0)
        net = gross - cost_return
        gross_returns.iloc[exit_i] += gross
        net_returns.iloc[exit_i] += net
        setup_reason = signals['reason'].iloc[i - 1] if i > 0 else signals['reason'].iloc[i]
        records.append(
            {
                'entry_time': ts,
                'exit_time': idx[exit_i],
                'side': side,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'gross_return': gross,
                'cost_return': cost_return,
                'net_return': net,
                'hold_bars': exit_i - i,
                'exit_reason': exit_reason,
                'reason': setup_reason,
            }
        )
        in_trade_until = exit_i
    return gross_returns, net_returns, pd.DataFrame.from_records(
        records,
        columns=[
            'entry_time',
            'exit_time',
            'side',
            'entry_price',
            'exit_price',
            'gross_return',
            'cost_return',
            'net_return',
            'hold_bars',
            'exit_reason',
            'reason',
        ],
    )


def _round_trip_cost(*, fee_bps: float, spread_bps: float, slippage_bps: float) -> float:
    values = [fee_bps, spread_bps, slippage_bps]
    if any((not np.isfinite(value) or value < 0) for value in values):
        raise ValueError('fee_bps, spread_bps, and slippage_bps must be finite non-negative values')
    return float((fee_bps + spread_bps + slippage_bps) / 10_000.0)


def _compute_metrics(
    net_returns: pd.Series,
    gross_returns: pd.Series,
    trades: pd.DataFrame,
    signals: pd.DataFrame,
    *,
    periods_per_year: int,
) -> dict[str, float | int]:
    trade_returns = trades['net_return'].astype(float) if not trades.empty else pd.Series(dtype=float)
    gross_trade_returns = trades['gross_return'].astype(float) if not trades.empty else pd.Series(dtype=float)
    net_total_return = float((1.0 + net_returns).prod() - 1.0)
    gross_total_return = float((1.0 + gross_returns).prod() - 1.0)
    years = len(net_returns) / periods_per_year if periods_per_year > 0 else 0.0
    annualized_return = 0.0
    if years > 0 and net_total_return > -1.0:
        annual_log_return = float(np.log1p(net_total_return) / years)
        annualized_return = float(np.expm1(min(annual_log_return, 700.0)))
    std = float(net_returns.std(ddof=0))
    sharpe = float((net_returns.mean() / std) * np.sqrt(periods_per_year)) if std > 0 else 0.0
    equity = (1.0 + net_returns).cumprod()
    drawdown = equity / equity.cummax() - 1.0
    wins = int((trade_returns > 0).sum())
    losses = int((trade_returns < 0).sum())
    count = int(len(trade_returns))
    return {
        'bars': int(len(net_returns)),
        'trades': count,
        'long_trades': int((trades['side'] == 1).sum()) if not trades.empty else 0,
        'short_trades': int((trades['side'] == -1).sum()) if not trades.empty else 0,
        'wins': wins,
        'losses': losses,
        'win_rate': float(wins / count) if count else 0.0,
        'gross_total_return': gross_total_return,
        'net_total_return': net_total_return,
        'annualized_return': annualized_return,
        'sharpe': sharpe,
        'max_drawdown': float(drawdown.min()) if len(drawdown) else 0.0,
        'average_trade_return': float(trade_returns.mean()) if count else 0.0,
        'exposure': float((signals['execution_signal'] != 0).mean()) if len(signals) else 0.0,
        'average_gross_trade_return': float(gross_trade_returns.mean()) if count else 0.0,
    }


def _format_summary(report: dict[str, Any]) -> str:
    metrics = report['metrics']
    return '\n'.join(
        [
            f"Strategy: {report['strategy']}",
            f"Data: {report['data_source']}",
            (
                'Metrics: '
                f"trades={metrics['trades']} "
                f"win_rate={metrics['win_rate']:.2%} "
                f"gross_total_return={metrics['gross_total_return']:.2%} "
                f"net_total_return={metrics['net_total_return']:.2%} "
                f"sharpe={metrics['sharpe']:.2f} "
                f"max_drawdown={metrics['max_drawdown']:.2%}"
            ),
        ]
    )


def _frame_to_json_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    records = frame.copy()
    for column in records.columns:
        if pd.api.types.is_datetime64_any_dtype(records[column]):
            records[column] = records[column].dt.strftime('%Y-%m-%dT%H:%M:%S')
    return records.to_dict(orient='records')


def _describe_data_source(data: pd.DataFrame | str | Path) -> str:
    if isinstance(data, (str, Path)):
        return str(data)
    return 'dataframe'


if __name__ == '__main__':  # pragma: no cover
    raise SystemExit(main())
