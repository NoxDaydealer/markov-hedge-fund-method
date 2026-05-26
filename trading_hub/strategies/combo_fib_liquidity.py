from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd

OHLCV_COLUMNS = ('open', 'high', 'low', 'close', 'volume')
SignalSide = Literal[-1, 0, 1]


@dataclass(frozen=True)
class ComboFibLiquidityAdapter:
    """Paper-only adapter for the combo_fib_liquidity TradingEngine strategy.

    The adapter is intentionally pure and local: it accepts caller-supplied OHLCV
    data, derives trailing-only indicators, and returns paper execution intents.
    It does not fetch market data, touch broker APIs, or place orders.

    Signal summary:
    - Long setup: current bar sweeps below prior trailing liquidity low, trades
      into the Fibonacci retracement zone, then closes back inside the prior
      liquidity range.
    - Short setup: mirror image against the prior trailing liquidity high.
      Shorts are suppressed unless explicitly enabled.
    - Markov gate: longs require non-negative Markov risk signal; shorts require
      negative Markov risk signal and enable_shorts=True.
    - Execution: today's accepted signal is shifted to the next bar and filled at
      the next bar open, avoiding same-bar lookahead.
    """

    lookback: int = 20
    atr_period: int = 14
    markov_signal: float | None = None
    enable_shorts: bool = False
    atr_stop_multiple: float = 1.0
    atr_take_profit_multiple: float = 2.0

    def generate_signals(self, data: pd.DataFrame | str | Path) -> pd.DataFrame:
        frame = self._load_ohlcv(data)
        if self.lookback < 2:
            raise ValueError('lookback must be at least 2')
        if self.atr_period < 1:
            raise ValueError('atr_period must be at least 1')

        self._validate_parameters()
        indicators = self.indicators(frame)
        raw_signal, ambiguous_setup = self._raw_signals(frame, indicators)
        markov_allowed_bool = raw_signal.map(self._markov_allows).astype(bool)
        markov_allowed = markov_allowed_bool.astype(object)

        signal = raw_signal.where(markov_allowed_bool, 0).astype(int)

        execution_signal = signal.shift(1, fill_value=0).astype(int)
        execution_price = frame['open'].where(execution_signal != 0)
        atr_for_execution = indicators['atr'].shift(1)

        stop_price = pd.Series(pd.NA, index=frame.index, dtype='Float64')
        take_profit_price = pd.Series(pd.NA, index=frame.index, dtype='Float64')
        long_exec = execution_signal == 1
        short_exec = execution_signal == -1
        stop_price.loc[long_exec] = execution_price.loc[long_exec] - (
            self.atr_stop_multiple * atr_for_execution.loc[long_exec]
        )
        take_profit_price.loc[long_exec] = execution_price.loc[long_exec] + (
            self.atr_take_profit_multiple * atr_for_execution.loc[long_exec]
        )
        stop_price.loc[short_exec] = execution_price.loc[short_exec] + (
            self.atr_stop_multiple * atr_for_execution.loc[short_exec]
        )
        take_profit_price.loc[short_exec] = execution_price.loc[short_exec] - (
            self.atr_take_profit_multiple * atr_for_execution.loc[short_exec]
        )

        reason = pd.Series('', index=frame.index, dtype=object)
        reason.loc[raw_signal == 1] = 'long_liquidity_sweep_fib_reclaim'
        reason.loc[raw_signal == -1] = 'short_liquidity_sweep_fib_reject'
        reason.loc[(raw_signal != 0) & ~markov_allowed_bool] = 'blocked_by_markov_regime_gate'
        reason.loc[ambiguous_setup] = 'ambiguous_long_and_short_setup'
        markov_signal = self.markov_signal
        if markov_signal is not None and markov_signal < 0 and not self.enable_shorts:
            shorts_disabled = raw_signal == -1
        else:
            shorts_disabled = pd.Series(False, index=frame.index)
        reason.loc[shorts_disabled] = 'blocked_shorts_disabled'

        return pd.DataFrame(
            {
                'raw_signal': raw_signal.astype(int),
                'markov_allowed': markov_allowed,
                'signal': signal,
                'execution_signal': execution_signal,
                'execution_price': execution_price.astype('Float64'),
                'stop_price': stop_price,
                'take_profit_price': take_profit_price,
                'reason': reason,
            },
            index=frame.index,
        )

    def indicators(self, data: pd.DataFrame | str | Path) -> pd.DataFrame:
        frame = self._load_ohlcv(data)
        prior_high = frame['high'].shift(1).rolling(self.lookback, min_periods=self.lookback).max()
        prior_low = frame['low'].shift(1).rolling(self.lookback, min_periods=self.lookback).min()
        prior_range = prior_high - prior_low

        previous_close = frame['close'].shift(1)
        true_range = pd.concat(
            [
                frame['high'] - frame['low'],
                (frame['high'] - previous_close).abs(),
                (frame['low'] - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = true_range.rolling(self.atr_period, min_periods=self.atr_period).mean()

        return pd.DataFrame(
            {
                'prior_liquidity_high': prior_high,
                'prior_liquidity_low': prior_low,
                'fib_382': prior_low + (prior_range * 0.382),
                'fib_618': prior_low + (prior_range * 0.618),
                'atr': atr,
            },
            index=frame.index,
        )

    def _raw_signals(self, frame: pd.DataFrame, indicators: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        swept_low = frame['low'] < indicators['prior_liquidity_low']
        crossed_long_fib_zone = (frame['low'] <= indicators['fib_618']) & (frame['high'] >= indicators['fib_618'])
        reclaimed_liquidity_range = frame['close'] > indicators['prior_liquidity_low']
        bullish_reclaim = frame['close'] > frame['open']
        swept_high = frame['high'] > indicators['prior_liquidity_high']
        crossed_short_fib_zone = (frame['high'] >= indicators['fib_382']) & (frame['low'] <= indicators['fib_382'])
        rejected_liquidity_range = frame['close'] < indicators['prior_liquidity_high']
        bearish_reject = frame['close'] < frame['open']

        long_candidate = swept_low & crossed_long_fib_zone & reclaimed_liquidity_range
        short_candidate = swept_high & crossed_short_fib_zone & rejected_liquidity_range
        long_setup = long_candidate & bullish_reclaim
        short_setup = short_candidate & bearish_reject
        ambiguous_setup = long_candidate & short_candidate

        raw = pd.Series(0, index=frame.index, dtype=int)
        raw.loc[long_setup & ~ambiguous_setup] = 1
        raw.loc[short_setup & ~ambiguous_setup] = -1
        return raw, ambiguous_setup

    def _validate_parameters(self) -> None:
        if not pd.notna(self.atr_stop_multiple) or self.atr_stop_multiple <= 0:
            raise ValueError('atr_stop_multiple must be finite and greater than 0')
        if not pd.notna(self.atr_take_profit_multiple) or self.atr_take_profit_multiple <= 0:
            raise ValueError('atr_take_profit_multiple must be finite and greater than 0')
        if self.markov_signal is not None and not pd.notna(self.markov_signal):
            raise ValueError('markov_signal must be finite when provided')

    def _markov_allows(self, side: SignalSide) -> bool:
        if side == 0:
            return True
        if side == 1:
            return self.markov_signal is None or self.markov_signal >= 0
        return self.enable_shorts and self.markov_signal is not None and self.markov_signal < 0

    def _load_ohlcv(self, data: pd.DataFrame | str | Path) -> pd.DataFrame:
        if isinstance(data, (str, Path)):
            frame = pd.read_csv(data)
            date_col = _find_column(frame, ('date', 'time', 'timestamp', 'datetime'))
            if date_col is not None:
                frame[date_col] = pd.to_datetime(frame[date_col], errors='coerce')
                frame = frame.dropna(subset=[date_col]).set_index(date_col)
                frame.index.name = None
        else:
            frame = data.copy()

        rename = {column: str(column).strip().lower().replace(' ', '_') for column in frame.columns}
        frame = frame.rename(columns=rename)
        missing = [column for column in OHLCV_COLUMNS if column not in frame.columns]
        if missing:
            raise ValueError(f'OHLCV data missing required columns: {missing}')

        frame = frame.loc[:, list(OHLCV_COLUMNS)].copy()
        for column in OHLCV_COLUMNS:
            frame[column] = pd.to_numeric(frame[column], errors='coerce')
        frame = frame.dropna(subset=list(OHLCV_COLUMNS))
        if frame.empty:
            raise ValueError('OHLCV data has no usable rows')
        if (frame['high'] < frame['low']).any():
            raise ValueError('OHLCV data invalid: high must be greater than or equal to low')
        if (frame['open'] > frame['high']).any() or (frame['open'] < frame['low']).any():
            raise ValueError('OHLCV data invalid: open must be inside high/low range')
        if (frame['close'] > frame['high']).any() or (frame['close'] < frame['low']).any():
            raise ValueError('OHLCV data invalid: close must be inside high/low range')
        if not frame.index.is_monotonic_increasing:
            frame = frame.sort_index()
        if isinstance(frame.index, pd.DatetimeIndex):
            frame.index.freq = None
        return frame


def generate_combo_fib_liquidity_signals(
    data: pd.DataFrame | str | Path,
    **kwargs,
) -> pd.DataFrame:
    """Convenience functional API for paper combo_fib_liquidity signals."""

    return ComboFibLiquidityAdapter(**kwargs).generate_signals(data)


def _find_column(frame: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    by_normalized = {str(column).strip().lower().replace(' ', '_'): column for column in frame.columns}
    for candidate in candidates:
        if candidate in by_normalized:
            return by_normalized[candidate]
    return None
