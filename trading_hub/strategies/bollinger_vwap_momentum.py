from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from trading_hub.strategies.combo_fib_liquidity import OHLCV_COLUMNS, _find_column


@dataclass(frozen=True)
class BollingerVwapMomentumAdapter:
    """Pure local, paper-only Bollinger/VWAP/momentum strategy adapter.

    The adapter accepts caller-supplied OHLCV data or a local CSV path, derives
    trailing indicators only, and emits next-bar paper execution intents. It does
    not fetch market data, call broker APIs, or place orders.
    """

    bb_period: int = 20
    bb_stddev: float = 2.0
    bandwidth_percentile_window: int = 100
    bandwidth_percentile_threshold: float = 0.20
    volume_window: int = 20
    volume_multiplier: float = 1.5
    rsi_period: int = 14
    rsi_long_threshold: float = 55.0
    rsi_short_threshold: float = 45.0
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    atr_period: int = 14
    atr_trailing_multiple: float = 2.0
    max_holding_bars: int = 30
    enable_shorts: bool = False

    def generate_signals(self, data: pd.DataFrame | str | Path) -> pd.DataFrame:
        frame = self._load_ohlcv(data)
        self._validate_parameters()
        indicators = self.indicators(frame)
        raw_signal, reason = self._raw_signals(frame, indicators)
        signal = raw_signal.copy()
        if not self.enable_shorts:
            signal = signal.where(signal >= 0, 0)

        execution_signal = signal.shift(1, fill_value=0).astype(int)
        execution_price = frame['open'].where(execution_signal != 0)
        reason = reason.copy()
        reason.loc[(raw_signal == -1) & (signal == 0)] = 'blocked_shorts_disabled'

        return pd.DataFrame(
            {
                'raw_signal': raw_signal.astype(int),
                'signal': signal.astype(int),
                'execution_signal': execution_signal,
                'execution_price': execution_price.astype('Float64'),
                'vwap': indicators['vwap'].astype('Float64'),
                'bb_upper': indicators['bb_upper'].astype('Float64'),
                'bb_lower': indicators['bb_lower'].astype('Float64'),
                'bb_bandwidth_percentile': indicators['bb_bandwidth_percentile'].astype('Float64'),
                'rsi': indicators['rsi'].astype('Float64'),
                'macd': indicators['macd'].astype('Float64'),
                'macd_signal': indicators['macd_signal'].astype('Float64'),
                'atr': indicators['atr'].astype('Float64'),
                'reason': reason,
            },
            index=frame.index,
        )

    def indicators(self, data: pd.DataFrame | str | Path) -> pd.DataFrame:
        frame = self._load_ohlcv(data)
        typical_price = (frame['high'] + frame['low'] + frame['close']) / 3.0
        cumulative_volume = frame['volume'].cumsum().replace(0, np.nan)
        vwap = (typical_price * frame['volume']).cumsum() / cumulative_volume

        middle = frame['close'].rolling(self.bb_period, min_periods=self.bb_period).mean()
        std = frame['close'].rolling(self.bb_period, min_periods=self.bb_period).std(ddof=0)
        upper = middle + self.bb_stddev * std
        lower = middle - self.bb_stddev * std
        bandwidth = (upper - lower) / middle.replace(0, np.nan)
        bandwidth_percentile = bandwidth.rolling(
            self.bandwidth_percentile_window,
            min_periods=self.bandwidth_percentile_window,
        ).apply(_last_value_percentile, raw=True)

        volume_average = frame['volume'].rolling(self.volume_window, min_periods=self.volume_window).mean()
        rsi = _rsi(frame['close'], self.rsi_period)
        macd_line, macd_signal_line = _macd(frame['close'], self.macd_fast, self.macd_slow, self.macd_signal)
        atr = _atr(frame, self.atr_period)

        return pd.DataFrame(
            {
                'vwap': vwap,
                'bb_middle': middle,
                'bb_upper': upper,
                'bb_lower': lower,
                'bb_bandwidth': bandwidth,
                'bb_bandwidth_percentile': bandwidth_percentile,
                'volume_average': volume_average,
                'rsi': rsi,
                'macd': macd_line,
                'macd_signal': macd_signal_line,
                'atr': atr,
            },
            index=frame.index,
        )

    def _raw_signals(self, frame: pd.DataFrame, indicators: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        prior_squeeze = indicators['bb_bandwidth_percentile'].shift(1) <= self.bandwidth_percentile_threshold
        expanding_bandwidth = indicators['bb_bandwidth'] > indicators['bb_bandwidth'].shift(1)
        volume_expansion = frame['volume'] > (indicators['volume_average'].shift(1) * self.volume_multiplier)
        bullish_momentum = (indicators['rsi'] >= self.rsi_long_threshold) & (
            indicators['macd'] > indicators['macd_signal']
        )
        bearish_momentum = (indicators['rsi'] <= self.rsi_short_threshold) & (
            indicators['macd'] < indicators['macd_signal']
        )

        long_setup = (
            prior_squeeze
            & expanding_bandwidth
            & (frame['close'] > indicators['bb_upper'].shift(1))
            & (frame['close'] > indicators['vwap'])
            & volume_expansion
            & bullish_momentum
        )
        short_setup = (
            prior_squeeze
            & expanding_bandwidth
            & (frame['close'] < indicators['bb_lower'].shift(1))
            & (frame['close'] < indicators['vwap'])
            & volume_expansion
            & bearish_momentum
        )

        raw = pd.Series(0, index=frame.index, dtype=int)
        raw.loc[long_setup] = 1
        raw.loc[short_setup] = -1
        reason = pd.Series('', index=frame.index, dtype=object)
        reason.loc[long_setup] = 'long_bollinger_vwap_momentum_breakout'
        reason.loc[short_setup] = 'short_bollinger_vwap_momentum_breakout'
        return raw, reason

    def _validate_parameters(self) -> None:
        positive_ints = {
            'bb_period': self.bb_period,
            'bandwidth_percentile_window': self.bandwidth_percentile_window,
            'volume_window': self.volume_window,
            'rsi_period': self.rsi_period,
            'macd_fast': self.macd_fast,
            'macd_slow': self.macd_slow,
            'macd_signal': self.macd_signal,
            'atr_period': self.atr_period,
            'max_holding_bars': self.max_holding_bars,
        }
        for name, value in positive_ints.items():
            if int(value) != value or value < 1:
                raise ValueError(f'{name} must be a positive integer')
        if self.macd_fast >= self.macd_slow:
            raise ValueError('macd_fast must be less than macd_slow')
        positive_floats = {
            'bb_stddev': self.bb_stddev,
            'volume_multiplier': self.volume_multiplier,
            'atr_trailing_multiple': self.atr_trailing_multiple,
        }
        for name, value in positive_floats.items():
            if not pd.notna(value) or value <= 0:
                raise ValueError(f'{name} must be finite and greater than 0')
        if not 0 <= self.bandwidth_percentile_threshold <= 1:
            raise ValueError('bandwidth_percentile_threshold must be between 0 and 1')

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


def generate_bollinger_vwap_momentum_signals(
    data: pd.DataFrame | str | Path,
    **kwargs: Any,
) -> pd.DataFrame:
    return BollingerVwapMomentumAdapter(**kwargs).generate_signals(data)


def _last_value_percentile(values: np.ndarray) -> float:
    valid = values[~np.isnan(values)]
    if len(valid) == 0:
        return np.nan
    return float((valid <= valid[-1]).sum() / len(valid))


def _rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).rolling(period, min_periods=period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(100.0).where(gain.notna())


def _macd(close: pd.Series, fast: int, slow: int, signal: int) -> tuple[pd.Series, pd.Series]:
    fast_ema = close.ewm(span=fast, adjust=False, min_periods=fast).mean()
    slow_ema = close.ewm(span=slow, adjust=False, min_periods=slow).mean()
    macd_line = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return macd_line, signal_line


def _atr(frame: pd.DataFrame, period: int) -> pd.Series:
    previous_close = frame['close'].shift(1)
    true_range = pd.concat(
        [
            frame['high'] - frame['low'],
            (frame['high'] - previous_close).abs(),
            (frame['low'] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.rolling(period, min_periods=period).mean()
