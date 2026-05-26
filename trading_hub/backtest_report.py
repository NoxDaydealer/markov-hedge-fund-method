from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from trading_hub.strategies.bollinger_vwap_momentum import BollingerVwapMomentumAdapter
from trading_hub.strategies.combo_fib_liquidity import ComboFibLiquidityAdapter


@dataclass(frozen=True)
class BacktestResult:
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


@dataclass(frozen=True)
class DataBundle:
    frame: pd.DataFrame
    source: str


def run_combo_fib_liquidity_backtest(
    data: pd.DataFrame | str | Path,
    *,
    data_source: str | None = None,
    periods_per_year: int = 252,
    **adapter_kwargs: Any,
) -> BacktestResult:
    """Run a paper-only no-lookahead next-bar backtest for combo_fib_liquidity.

    Signals are generated from each completed setup bar by the adapter and shifted
    into ``execution_signal`` on the next bar. Returns are then computed from the
    execution bar open to the following bar open. An execution on the final row is
    ignored because its next-bar return is unknowable in a no-lookahead report.
    """

    adapter = ComboFibLiquidityAdapter(**adapter_kwargs)
    frame = adapter._load_ohlcv(data)
    signals = adapter.generate_signals(frame)

    next_open_return = frame['open'].shift(-1) / frame['open'] - 1.0
    trade_mask = (signals['execution_signal'] != 0) & next_open_return.notna()
    strategy_returns = (signals['execution_signal'] * next_open_return).where(trade_mask, 0.0).astype(float)
    equity_curve = (1.0 + strategy_returns).cumprod()
    trades = _build_trades(frame, signals, next_open_return, trade_mask)
    metrics = _compute_metrics(strategy_returns, trades, periods_per_year=periods_per_year)

    return BacktestResult(
        strategy='combo_fib_liquidity',
        data_source=data_source if data_source is not None else _describe_data_source(data),
        metrics=metrics,
        signals=signals,
        trades=trades,
        equity_curve=equity_curve,
    )


def run_bollinger_vwap_momentum_backtest(
    data: pd.DataFrame | str | Path,
    *,
    data_source: str | None = None,
    periods_per_year: int = 252 * 390,
    fee_bps: float = 0.0,
    spread_bps: float = 0.0,
    slippage_bps: float = 0.0,
    **adapter_kwargs: Any,
) -> BacktestResult:
    """Run a paper-only Bollinger/VWAP/momentum backtest with local OHLCV data.

    Entries use the adapter's next-bar ``execution_signal``. Open positions exit
    on ATR trailing stop first, then VWAP recross, then max holding bars, with a
    final end-of-data close for any still-open position. Fees/spread/slippage are
    modeled as bps hooks per side; no broker orders are placed.
    """

    adapter = BollingerVwapMomentumAdapter(**adapter_kwargs)
    frame = adapter._load_ohlcv(data)
    signals = adapter.generate_signals(frame)
    trades = _build_bollinger_vwap_momentum_trades(
        frame,
        signals,
        max_holding_bars=adapter.max_holding_bars,
        atr_trailing_multiple=adapter.atr_trailing_multiple,
        fee_bps=fee_bps,
        spread_bps=spread_bps,
        slippage_bps=slippage_bps,
    )
    strategy_returns = pd.Series(0.0, index=frame.index)
    for _, trade in trades.iterrows():
        strategy_returns.at[trade['exit_time']] += float(trade['return'])
    equity_curve = (1.0 + strategy_returns).cumprod()
    metrics = _compute_metrics(strategy_returns, trades, periods_per_year=periods_per_year)

    return BacktestResult(
        strategy='bollinger_vwap_momentum',
        data_source=data_source if data_source is not None else _describe_data_source(data),
        metrics=metrics,
        signals=signals,
        trades=trades,
        equity_curve=equity_curve,
    )


def load_csv(path: str | Path) -> DataBundle:
    return DataBundle(frame=pd.read_csv(path), source=str(path))


def load_yfinance(symbol: str, *, period: str = '1y', interval: str = '1d') -> DataBundle:
    """Fetch OHLCV through yfinance only when the CLI explicitly asks for it."""

    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover - depends on optional env
        raise RuntimeError('yfinance is required for --ticker; install it or use --csv') from exc

    frame = yf.download(symbol, period=period, interval=interval, auto_adjust=False, progress=False)
    if frame is None or frame.empty:
        raise ValueError(f'yfinance returned no rows for {symbol}')
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = [str(column[0]) for column in frame.columns]
    return DataBundle(frame=frame, source=f'yfinance:{symbol}:{period}:{interval}')


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if bool(args.csv) == bool(args.ticker):
        parser.error('provide exactly one of --csv or --ticker')

    bundle = load_csv(args.csv) if args.csv else load_yfinance(args.ticker, period=args.period, interval=args.interval)
    if args.strategy == 'combo_fib_liquidity':
        result = run_combo_fib_liquidity_backtest(
            bundle.frame,
            data_source=bundle.source,
            lookback=args.lookback,
            atr_period=args.atr_period,
            markov_signal=args.markov_signal,
            enable_shorts=args.enable_shorts,
            atr_stop_multiple=args.atr_stop_multiple,
            atr_take_profit_multiple=args.atr_take_profit_multiple,
            periods_per_year=args.periods_per_year,
        )
    else:
        result = run_bollinger_vwap_momentum_backtest(
            bundle.frame,
            data_source=bundle.source,
            bb_period=args.bb_period,
            bb_stddev=args.bb_stddev,
            bandwidth_percentile_window=args.bandwidth_percentile_window,
            bandwidth_percentile_threshold=args.bandwidth_percentile_threshold,
            volume_window=args.volume_window,
            volume_multiplier=args.volume_multiplier,
            rsi_period=args.rsi_period,
            rsi_long_threshold=args.rsi_long_threshold,
            rsi_short_threshold=args.rsi_short_threshold,
            macd_fast=args.macd_fast,
            macd_slow=args.macd_slow,
            macd_signal=args.macd_signal,
            atr_period=args.atr_period,
            atr_trailing_multiple=args.atr_trailing_multiple,
            max_holding_bars=args.max_holding_bars,
            enable_shorts=args.enable_shorts,
            periods_per_year=args.periods_per_year,
            fee_bps=args.fee_bps,
            spread_bps=args.spread_bps,
            slippage_bps=args.slippage_bps,
        )

    report = result.to_dict()
    if args.output_json:
        Path(args.output_json).write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(_format_summary(report))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Paper-only local strategy backtest/report runner')
    parser.add_argument(
        '--strategy',
        choices=['combo_fib_liquidity', 'bollinger_vwap_momentum'],
        default='combo_fib_liquidity',
        help='Local paper strategy adapter to run',
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--csv', help='Local OHLCV CSV path. No network calls are made for this mode.')
    source.add_argument('--ticker', help='Explicit yfinance ticker to fetch, e.g. SPY. Optional network mode.')
    parser.add_argument('--period', default='1y', help='yfinance period when --ticker is used')
    parser.add_argument('--interval', default='1d', help='yfinance interval when --ticker is used')
    parser.add_argument('--lookback', type=int, default=20)
    parser.add_argument('--atr-period', type=int, default=14)
    parser.add_argument('--markov-signal', type=float, default=None)
    parser.add_argument('--enable-shorts', action='store_true')
    parser.add_argument('--atr-stop-multiple', type=float, default=1.0)
    parser.add_argument('--atr-take-profit-multiple', type=float, default=2.0)
    parser.add_argument('--bb-period', type=int, default=20)
    parser.add_argument('--bb-stddev', type=float, default=2.0)
    parser.add_argument('--bandwidth-percentile-window', type=int, default=100)
    parser.add_argument('--bandwidth-percentile-threshold', type=float, default=0.20)
    parser.add_argument('--volume-window', type=int, default=20)
    parser.add_argument('--volume-multiplier', type=float, default=1.5)
    parser.add_argument('--rsi-period', type=int, default=14)
    parser.add_argument('--rsi-long-threshold', type=float, default=55.0)
    parser.add_argument('--rsi-short-threshold', type=float, default=45.0)
    parser.add_argument('--macd-fast', type=int, default=12)
    parser.add_argument('--macd-slow', type=int, default=26)
    parser.add_argument('--macd-signal', type=int, default=9)
    parser.add_argument('--atr-trailing-multiple', type=float, default=2.0)
    parser.add_argument('--max-holding-bars', type=int, default=30)
    parser.add_argument('--fee-bps', type=float, default=0.0)
    parser.add_argument('--spread-bps', type=float, default=0.0)
    parser.add_argument('--slippage-bps', type=float, default=0.0)
    parser.add_argument('--periods-per-year', type=int, default=252)
    parser.add_argument('--output-json', help='Optional path to write machine-readable report JSON')
    return parser


def _build_trades(
    frame: pd.DataFrame,
    signals: pd.DataFrame,
    next_open_return: pd.Series,
    trade_mask: pd.Series,
) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for row_number, (timestamp, active) in enumerate(trade_mask.items()):
        if not active:
            continue
        side = int(signals.at[timestamp, 'execution_signal'])
        setup_reason = signals['reason'].iloc[row_number - 1] if row_number > 0 else signals.at[timestamp, 'reason']
        records.append(
            {
                'entry_time': timestamp,
                'exit_time': frame.index[row_number + 1],
                'side': side,
                'entry_price': float(frame.at[timestamp, 'open']),
                'exit_price': float(frame['open'].iloc[row_number + 1]),
                'return': float(side * next_open_return.at[timestamp]),
                'reason': setup_reason,
            }
        )
    return pd.DataFrame.from_records(
        records,
        columns=['entry_time', 'exit_time', 'side', 'entry_price', 'exit_price', 'return', 'reason'],
    )


def _build_bollinger_vwap_momentum_trades(
    frame: pd.DataFrame,
    signals: pd.DataFrame,
    *,
    max_holding_bars: int,
    atr_trailing_multiple: float,
    fee_bps: float,
    spread_bps: float,
    slippage_bps: float,
) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    row = 0
    round_trip_cost = 2.0 * (fee_bps + spread_bps + slippage_bps) / 10_000.0
    while row < len(frame):
        side = int(signals['execution_signal'].iloc[row])
        if side == 0:
            row += 1
            continue

        entry_row = row
        entry_time = frame.index[entry_row]
        entry_price = float(frame['open'].iloc[entry_row])
        entry_atr = signals['atr'].iloc[entry_row]
        if pd.isna(entry_atr):
            row += 1
            continue

        if side == 1:
            trailing_stop = entry_price - (atr_trailing_multiple * float(entry_atr))
        else:
            trailing_stop = entry_price + (atr_trailing_multiple * float(entry_atr))
        exit_row = len(frame) - 1
        exit_price = float(frame['close'].iloc[-1])
        exit_reason = 'end_of_data'

        for scan_row in range(entry_row + 1, len(frame)):
            atr_value = signals['atr'].iloc[scan_row]
            if not pd.isna(atr_value):
                if side == 1:
                    trailing_stop = max(
                        trailing_stop,
                        float(frame['high'].iloc[scan_row]) - (atr_trailing_multiple * float(atr_value)),
                    )
                else:
                    trailing_stop = min(
                        trailing_stop,
                        float(frame['low'].iloc[scan_row]) + (atr_trailing_multiple * float(atr_value)),
                    )

            if side == 1 and float(frame['low'].iloc[scan_row]) <= trailing_stop:
                exit_row = scan_row
                exit_price = trailing_stop
                exit_reason = 'atr_trailing_stop'
                break
            if side == -1 and float(frame['high'].iloc[scan_row]) >= trailing_stop:
                exit_row = scan_row
                exit_price = trailing_stop
                exit_reason = 'atr_trailing_stop'
                break

            vwap_value = signals['vwap'].iloc[scan_row]
            if side == 1 and not pd.isna(vwap_value) and float(frame['close'].iloc[scan_row]) < float(vwap_value):
                exit_row = scan_row
                exit_price = float(frame['close'].iloc[scan_row])
                exit_reason = 'vwap_recross'
                break
            if side == -1 and not pd.isna(vwap_value) and float(frame['close'].iloc[scan_row]) > float(vwap_value):
                exit_row = scan_row
                exit_price = float(frame['close'].iloc[scan_row])
                exit_reason = 'vwap_recross'
                break

            if scan_row - entry_row >= max_holding_bars:
                exit_row = scan_row
                exit_price = float(frame['close'].iloc[scan_row])
                exit_reason = 'time_stop'
                break

        gross_return = side * ((exit_price - entry_price) / entry_price)
        records.append(
            {
                'entry_time': entry_time,
                'exit_time': frame.index[exit_row],
                'side': side,
                'entry_price': entry_price,
                'exit_price': float(exit_price),
                'gross_return': float(gross_return),
                'cost_return': float(round_trip_cost),
                'return': float(gross_return - round_trip_cost),
                'exit_reason': exit_reason,
                'reason': signals['reason'].iloc[entry_row - 1] if entry_row > 0 else signals['reason'].iloc[entry_row],
            }
        )
        row = exit_row + 1

    return pd.DataFrame.from_records(
        records,
        columns=[
            'entry_time',
            'exit_time',
            'side',
            'entry_price',
            'exit_price',
            'gross_return',
            'cost_return',
            'return',
            'exit_reason',
            'reason',
        ],
    )


def _compute_metrics(strategy_returns: pd.Series, trades: pd.DataFrame, *, periods_per_year: int) -> dict[str, float | int]:
    trade_returns = trades['return'].astype(float) if not trades.empty else pd.Series(dtype=float)
    total_return = float((1.0 + strategy_returns).prod() - 1.0)
    years = len(strategy_returns) / periods_per_year if periods_per_year > 0 else 0.0
    annualized_return = float((1.0 + total_return) ** (1.0 / years) - 1.0) if years > 0 else 0.0
    std = float(strategy_returns.std(ddof=0))
    sharpe = float((strategy_returns.mean() / std) * np.sqrt(periods_per_year)) if std > 0 else 0.0
    equity = (1.0 + strategy_returns).cumprod()
    drawdown = equity / equity.cummax() - 1.0

    wins = int((trade_returns > 0).sum())
    losses = int((trade_returns < 0).sum())
    trades_count = int(len(trade_returns))
    return {
        'bars': int(len(strategy_returns)),
        'trades': trades_count,
        'wins': wins,
        'losses': losses,
        'win_rate': float(wins / trades_count) if trades_count else 0.0,
        'total_return': total_return,
        'annualized_return': annualized_return,
        'sharpe': sharpe,
        'max_drawdown': float(drawdown.min()) if len(drawdown) else 0.0,
        'average_trade_return': float(trade_returns.mean()) if trades_count else 0.0,
    }


def _format_summary(report: dict[str, Any]) -> str:
    metrics = report['metrics']
    lines = [
        f"Strategy: {report['strategy']}",
        f"Data: {report['data_source']}",
        (
            'Metrics: '
            f"trades={metrics['trades']} "
            f"win_rate={metrics['win_rate']:.2%} "
            f"total_return={metrics['total_return']:.2%} "
            f"annualized_return={metrics['annualized_return']:.2%} "
            f"sharpe={metrics['sharpe']:.2f} "
            f"max_drawdown={metrics['max_drawdown']:.2%}"
        ),
    ]
    return '\n'.join(lines)


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
