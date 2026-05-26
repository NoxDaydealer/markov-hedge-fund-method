from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

OHLCV_COLUMNS = ('open', 'high', 'low', 'close', 'volume')


@dataclass(frozen=True)
class VWAPVolumeReversionAdapter:
    """Pure local VWAP + volume + RSI/StochRSI mean-reversion adapter.

    The adapter accepts caller-supplied 1m/5m OHLCV data and produces paper-only
    next-bar execution intents. It never fetches data, touches broker APIs, or
    places orders.
    """

    vwap_window: int = 240
    z_window: int = 240
    rsi_period: int = 14
    stochrsi_period: int = 14
    volume_window: int = 60
    atr_period: int = 14
    z_threshold: float = 1.0
    rsi_long: float = 30.0
    rsi_short: float = 70.0
    stochrsi_long: float = 0.20
    stochrsi_short: float = 0.80
    volume_multiple: float = 1.5
    enable_shorts: bool = True
    atr_stop_multiple: float = 1.0
    atr_target_multiple: float = 1.5
    local_extreme_lookback: int = 3
    informative_5m: pd.DataFrame | str | Path | None = None
    five_min_rsi_long: float | None = None
    five_min_rsi_short: float | None = None

    def generate_signals(self, data: pd.DataFrame | str | Path) -> pd.DataFrame:
        frame = self._load_ohlcv(data)
        self._validate_parameters()
        indicators = self.indicators(frame)

        previous_high = frame['high'].shift(1)
        previous_low = frame['low'].shift(1)
        reclaimed_long = (frame['close'] > previous_high) & (frame['close'] > frame['open'])
        reclaimed_short = (frame['close'] < previous_low) & (frame['close'] < frame['open'])

        recent_z_min = indicators['vwap_distance_zscore'].rolling(
            self.local_extreme_lookback + 1,
            min_periods=1,
        ).min()
        recent_z_max = indicators['vwap_distance_zscore'].rolling(
            self.local_extreme_lookback + 1,
            min_periods=1,
        ).max()
        long_setup = (
            (recent_z_min <= -self.z_threshold)
            & (indicators['rsi'] <= self.rsi_long)
            & (indicators['stochrsi'] <= self.stochrsi_long)
            & indicators['volume_spike'].astype(bool)
            & reclaimed_long
        )
        short_setup = (
            (recent_z_max >= self.z_threshold)
            & (indicators['rsi'] >= self.rsi_short)
            & (indicators['stochrsi'] >= self.stochrsi_short)
            & indicators['volume_spike'].astype(bool)
            & reclaimed_short
            & self.enable_shorts
        )

        if self.informative_5m is not None:
            five_min_rsi = self._aligned_5m_rsi(frame.index)
            if self.five_min_rsi_long is not None:
                long_setup &= five_min_rsi <= self.five_min_rsi_long
            if self.five_min_rsi_short is not None:
                short_setup &= five_min_rsi >= self.five_min_rsi_short

        raw_signal = pd.Series(0, index=frame.index, dtype=int)
        ambiguous = long_setup & short_setup
        raw_signal.loc[long_setup & ~ambiguous] = 1
        raw_signal.loc[short_setup & ~ambiguous] = -1
        signal = raw_signal.copy()
        execution_signal = signal.shift(1, fill_value=0).astype(int)
        execution_price = frame['open'].where(execution_signal != 0)

        shifted_atr = indicators['atr'].shift(1)
        setup_low = frame['low'].shift(1).rolling(self.local_extreme_lookback, min_periods=1).min()
        setup_high = frame['high'].shift(1).rolling(self.local_extreme_lookback, min_periods=1).max()
        stop_price = pd.Series(pd.NA, index=frame.index, dtype='Float64')
        target_price = pd.Series(pd.NA, index=frame.index, dtype='Float64')
        long_exec = execution_signal == 1
        short_exec = execution_signal == -1
        long_atr_stop = execution_price - self.atr_stop_multiple * shifted_atr
        short_atr_stop = execution_price + self.atr_stop_multiple * shifted_atr
        stop_price.loc[long_exec] = pd.concat([long_atr_stop, setup_low], axis=1).max(axis=1).loc[long_exec]
        stop_price.loc[short_exec] = pd.concat([short_atr_stop, setup_high], axis=1).min(axis=1).loc[short_exec]
        long_atr_target = execution_price + self.atr_target_multiple * shifted_atr
        short_atr_target = execution_price - self.atr_target_multiple * shifted_atr
        target_price.loc[long_exec] = pd.concat([long_atr_target, indicators['vwap']], axis=1).min(axis=1).loc[long_exec]
        target_price.loc[short_exec] = pd.concat([short_atr_target, indicators['vwap']], axis=1).max(axis=1).loc[short_exec]

        reason = pd.Series('', index=frame.index, dtype=object)
        reason.loc[raw_signal == 1] = 'long_vwap_volume_rsi_reclaim'
        reason.loc[raw_signal == -1] = 'short_vwap_volume_rsi_reclaim'
        reason.loc[ambiguous] = 'ambiguous_long_and_short_setup'

        volume_spike = indicators['volume_spike'].astype(object)
        return pd.DataFrame(
            {
                'vwap': indicators['vwap'].astype('Float64'),
                'vwap_distance': indicators['vwap_distance'].astype('Float64'),
                'vwap_distance_zscore': indicators['vwap_distance_zscore'].astype('Float64'),
                'rsi': indicators['rsi'].astype('Float64'),
                'stochrsi': indicators['stochrsi'].astype('Float64'),
                'volume_spike': volume_spike,
                'raw_signal': raw_signal.astype(int),
                'signal': signal.astype(int),
                'execution_signal': execution_signal.astype(int),
                'execution_price': execution_price.astype('Float64'),
                'atr': indicators['atr'].astype('Float64'),
                'stop_price': stop_price,
                'target_price': target_price,
                'reason': reason,
            },
            index=frame.index,
        )

    def indicators(self, data: pd.DataFrame | str | Path) -> pd.DataFrame:
        frame = self._load_ohlcv(data)
        vwap = rolling_vwap(frame, self.vwap_window)
        distance = frame['close'] / vwap - 1.0
        distance_mean = distance.rolling(self.z_window, min_periods=self.z_window).mean()
        distance_std = distance.rolling(self.z_window, min_periods=self.z_window).std(ddof=0)
        zscore = (distance - distance_mean) / distance_std.replace(0, np.nan)
        rsi_values = rsi(frame['close'], self.rsi_period)
        rsi_min = rsi_values.rolling(self.stochrsi_period, min_periods=self.stochrsi_period).min()
        rsi_max = rsi_values.rolling(self.stochrsi_period, min_periods=self.stochrsi_period).max()
        stochrsi = ((rsi_values - rsi_min) / (rsi_max - rsi_min).replace(0, np.nan)).fillna(0.5)
        volume_baseline = frame['volume'].shift(1).rolling(self.volume_window, min_periods=self.volume_window).median()
        volume_spike = (frame['volume'] >= self.volume_multiple * volume_baseline).fillna(False)
        return pd.DataFrame(
            {
                'vwap': vwap,
                'vwap_distance': distance,
                'vwap_distance_zscore': zscore,
                'rsi': rsi_values,
                'stochrsi': stochrsi,
                'volume_spike': volume_spike,
                'atr': atr(frame, self.atr_period),
            },
            index=frame.index,
        )

    def _aligned_5m_rsi(self, index: pd.Index) -> pd.Series:
        if self.informative_5m is None:
            return pd.Series(50.0, index=index)
        frame_5m = self._load_ohlcv(self.informative_5m)
        values = rsi(frame_5m['close'], self.rsi_period)
        aligned = values.reindex(index, method='ffill')
        return aligned.fillna(50.0)

    def _validate_parameters(self) -> None:
        positive_ints = {
            'vwap_window': self.vwap_window,
            'z_window': self.z_window,
            'rsi_period': self.rsi_period,
            'stochrsi_period': self.stochrsi_period,
            'volume_window': self.volume_window,
            'atr_period': self.atr_period,
            'local_extreme_lookback': self.local_extreme_lookback,
        }
        for name, value in positive_ints.items():
            if value < 1:
                raise ValueError(f'{name} must be at least 1')
        for name in ('z_threshold', 'volume_multiple', 'atr_stop_multiple', 'atr_target_multiple'):
            value = float(getattr(self, name))
            if not np.isfinite(value) or value <= 0:
                raise ValueError(f'{name} must be finite and greater than 0')

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
        frame = frame.rename(columns={column: str(column).strip().lower().replace(' ', '_') for column in frame.columns})
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


def rolling_vwap(frame: pd.DataFrame, window: int) -> pd.Series:
    typical_price = (frame['high'] + frame['low'] + frame['close']) / 3.0
    volume = frame['volume']
    denominator = volume.rolling(window, min_periods=window).sum().replace(0, np.nan)
    return (typical_price * volume).rolling(window, min_periods=window).sum() / denominator


def rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50.0)


def atr(frame: pd.DataFrame, period: int) -> pd.Series:
    previous_close = frame['close'].shift(1)
    true_range = pd.concat(
        [
            frame['high'] - frame['low'],
            (frame['high'] - previous_close).abs(),
            (frame['low'] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def generate_vwap_volume_reversion_signals(data: pd.DataFrame | str | Path, **kwargs: object) -> pd.DataFrame:
    return VWAPVolumeReversionAdapter(**kwargs).generate_signals(data)


def _find_column(frame: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    normalized = {str(column).strip().lower().replace(' ', '_'): column for column in frame.columns}
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    return None
