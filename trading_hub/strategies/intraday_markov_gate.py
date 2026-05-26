from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

OHLCV_COLUMNS = ('open', 'high', 'low', 'close', 'volume')


@dataclass(frozen=True)
class IntradayMarkovRegimeGate:
    """Trailing-only intraday regime gate for HFT strategy candidates.

    The gate converts completed intraday bars into discrete feature regimes and a
    compact Markov state. Strategy selection and risk multipliers are designed as
    optimizer inputs, not as an execution engine. All rolling statistics use only
    the current and prior completed bars; executions consuming row ``t`` should be
    scheduled for row ``t+1`` by the caller.
    """

    lookback: int = 20
    min_train: int = 20
    high_spread_quantile: float = 0.80
    high_volume_quantile: float = 0.70
    high_volatility_quantile: float = 0.70
    vwap_distance_bps: float = 8.0
    imbalance_threshold: float = 0.20

    def generate(self, data: pd.DataFrame | str | Path) -> pd.DataFrame:
        frame = self._load_ohlcv(data)
        self._validate_parameters()

        features = self.build_features(frame)
        probabilities = self._markov_probabilities(features['markov_state'])
        decisions = self._decisions(features, probabilities)

        result = pd.concat([features, probabilities, decisions], axis=1)
        return result[
            [
                'return_regime',
                'volatility_regime',
                'spread_regime',
                'volume_regime',
                'vwap_distance_regime',
                'orderbook_imbalance_regime',
                'markov_state',
                'momentum_probability',
                'mean_reversion_probability',
                'selected_strategy',
                'trade_allowed',
                'threshold_multiplier',
                'stop_multiplier',
                'reason',
            ]
        ]

    def build_features(self, data: pd.DataFrame | str | Path) -> pd.DataFrame:
        frame = self._load_ohlcv(data)
        self._validate_parameters()

        returns = frame['close'].pct_change().fillna(0.0)
        rolling_return = frame['close'] / frame['close'].shift(self.lookback) - 1.0
        realized_volatility = returns.rolling(self.lookback, min_periods=self.lookback).std(ddof=0)
        typical_price = (frame['high'] + frame['low'] + frame['close']) / 3.0
        rolling_vwap = (typical_price * frame['volume']).rolling(
            self.lookback, min_periods=self.lookback
        ).sum() / frame['volume'].rolling(self.lookback, min_periods=self.lookback).sum()
        vwap_distance = (frame['close'] / rolling_vwap - 1.0).fillna(0.0)

        spread = self._spread_series(frame)
        spread_cutoff = spread.rolling(self.lookback, min_periods=self.lookback).quantile(self.high_spread_quantile)
        volume_cutoff = frame['volume'].rolling(self.lookback, min_periods=self.lookback).quantile(self.high_volume_quantile)
        volatility_cutoff = realized_volatility.rolling(
            self.lookback, min_periods=self.lookback
        ).quantile(self.high_volatility_quantile)

        return_regime = pd.Series('flat', index=frame.index, dtype=object)
        return_regime.loc[rolling_return > 0] = 'up'
        return_regime.loc[rolling_return < 0] = 'down'
        return_regime.loc[rolling_return.isna()] = 'unknown'

        volatility_regime = pd.Series('normal', index=frame.index, dtype=object)
        volatility_regime.loc[realized_volatility >= volatility_cutoff] = 'high'
        volatility_regime.loc[realized_volatility.isna()] = 'unknown'

        spread_regime = pd.Series('normal', index=frame.index, dtype=object)
        spread_regime.loc[spread >= spread_cutoff] = 'high'
        spread_regime.loc[spread.isna()] = 'unknown'

        volume_regime = pd.Series('normal', index=frame.index, dtype=object)
        volume_regime.loc[frame['volume'] >= volume_cutoff] = 'high'
        volume_regime.loc[frame['volume'].isna()] = 'unknown'

        vwap_distance_regime = pd.Series('near_vwap', index=frame.index, dtype=object)
        threshold = self.vwap_distance_bps / 10_000.0
        vwap_distance_regime.loc[vwap_distance > threshold] = 'above_vwap'
        vwap_distance_regime.loc[vwap_distance < -threshold] = 'below_vwap'
        vwap_distance_regime.loc[rolling_vwap.isna()] = 'unknown'

        orderbook_imbalance_regime = self._orderbook_imbalance_regime(frame)
        markov_state = (
            return_regime.astype(str)
            + '|vol:'
            + volatility_regime.astype(str)
            + '|spread:'
            + spread_regime.astype(str)
            + '|volume:'
            + volume_regime.astype(str)
            + '|vwap:'
            + vwap_distance_regime.astype(str)
            + '|ob:'
            + orderbook_imbalance_regime.astype(str)
        )

        return pd.DataFrame(
            {
                'return_regime': return_regime,
                'volatility_regime': volatility_regime,
                'spread_regime': spread_regime,
                'volume_regime': volume_regime,
                'vwap_distance_regime': vwap_distance_regime,
                'orderbook_imbalance_regime': orderbook_imbalance_regime,
                'markov_state': markov_state,
            },
            index=frame.index,
        )

    def _decisions(self, features: pd.DataFrame, probabilities: pd.DataFrame) -> pd.DataFrame:
        selected_strategy = pd.Series('flat', index=features.index, dtype=object)
        momentum_setup = (
            features['return_regime'].isin(['up', 'down'])
            & (features['volatility_regime'] != 'high')
            & (features['spread_regime'] != 'high')
        )
        mean_reversion_setup = (
            features['vwap_distance_regime'].isin(['above_vwap', 'below_vwap'])
            & features['volume_regime'].isin(['high', 'normal'])
            & (features['return_regime'] != 'unknown')
            & (features['spread_regime'] != 'high')
        )
        selected_strategy.loc[momentum_setup] = 'momentum'
        selected_strategy.loc[mean_reversion_setup] = 'mean_reversion'
        selected_strategy.loc[
            (probabilities['momentum_probability'] > probabilities['mean_reversion_probability'] + 0.10)
            & (features['spread_regime'] != 'high')
        ] = 'momentum'

        trade_allowed = pd.Series(True, index=features.index, dtype=object)
        blocked = features['spread_regime'] == 'high'
        trade_allowed.loc[blocked] = False

        threshold_multiplier = pd.Series(1.0, index=features.index, dtype=float)
        stop_multiplier = pd.Series(1.0, index=features.index, dtype=float)
        threshold_multiplier.loc[features['volatility_regime'] == 'high'] *= 1.25
        threshold_multiplier.loc[features['spread_regime'] == 'high'] *= 1.50
        threshold_multiplier.loc[selected_strategy == 'mean_reversion'] *= 1.15
        stop_multiplier.loc[features['volatility_regime'] == 'high'] *= 0.80
        stop_multiplier.loc[selected_strategy == 'mean_reversion'] *= 0.90
        stop_multiplier.loc[selected_strategy == 'momentum'] *= 1.10

        reason = pd.Series('ok', index=features.index, dtype=object)
        reason.loc[selected_strategy == 'flat'] = 'insufficient_or_neutral_regime'
        reason.loc[blocked] = 'blocked_high_spread_regime'

        return pd.DataFrame(
            {
                'selected_strategy': selected_strategy,
                'trade_allowed': trade_allowed,
                'threshold_multiplier': threshold_multiplier,
                'stop_multiplier': stop_multiplier,
                'reason': reason,
            },
            index=features.index,
        )

    def _markov_probabilities(self, states: pd.Series) -> pd.DataFrame:
        momentum_probability: list[float] = []
        mean_reversion_probability: list[float] = []
        prior_transitions: dict[str, dict[str, int]] = {}

        for i, state in enumerate(states.astype(str).tolist()):
            if i < self.min_train:
                momentum_probability.append(0.0)
                mean_reversion_probability.append(0.0)
            else:
                row = prior_transitions.get(state, {})
                total = sum(row.values())
                if total == 0:
                    momentum_probability.append(0.0)
                    mean_reversion_probability.append(0.0)
                else:
                    same_return_prefix = state.split('|', 1)[0]
                    momentum = sum(count for next_state, count in row.items() if next_state.startswith(same_return_prefix)) / total
                    mean_reversion = 1.0 - momentum
                    momentum_probability.append(float(momentum))
                    mean_reversion_probability.append(float(mean_reversion))

            if i > 0 and states.index[i - 1] is not None:
                prev_state = str(states.iloc[i - 1])
                bucket = prior_transitions.setdefault(prev_state, {})
                bucket[state] = bucket.get(state, 0) + 1

        return pd.DataFrame(
            {
                'momentum_probability': momentum_probability,
                'mean_reversion_probability': mean_reversion_probability,
            },
            index=states.index,
        )

    def _spread_series(self, frame: pd.DataFrame) -> pd.Series:
        for column in ('spread', 'bid_ask_spread', 'quoted_spread'):
            if column in frame.columns:
                return pd.to_numeric(frame[column], errors='coerce')
        return ((frame['high'] - frame['low']) / frame['close']).astype(float)

    def _orderbook_imbalance_regime(self, frame: pd.DataFrame) -> pd.Series:
        if 'orderbook_imbalance' in frame.columns:
            imbalance = pd.to_numeric(frame['orderbook_imbalance'], errors='coerce')
        elif 'bid_size' in frame.columns and 'ask_size' in frame.columns:
            bid = pd.to_numeric(frame['bid_size'], errors='coerce')
            ask = pd.to_numeric(frame['ask_size'], errors='coerce')
            denominator = bid + ask
            imbalance = ((bid - ask) / denominator).where(denominator != 0)
        else:
            return pd.Series('unknown', index=frame.index, dtype=object)

        regime = pd.Series('balanced', index=frame.index, dtype=object)
        regime.loc[imbalance >= self.imbalance_threshold] = 'bid_heavy'
        regime.loc[imbalance <= -self.imbalance_threshold] = 'ask_heavy'
        regime.loc[imbalance.isna()] = 'unknown'
        return regime

    def _validate_parameters(self) -> None:
        if self.lookback < 2:
            raise ValueError('lookback must be at least 2')
        if self.min_train < 1:
            raise ValueError('min_train must be at least 1')
        for name, value in (
            ('high_spread_quantile', self.high_spread_quantile),
            ('high_volume_quantile', self.high_volume_quantile),
            ('high_volatility_quantile', self.high_volatility_quantile),
        ):
            if not 0.0 < value < 1.0:
                raise ValueError(f'{name} must be between 0 and 1')
        if self.vwap_distance_bps < 0:
            raise ValueError('vwap_distance_bps must be non-negative')
        if self.imbalance_threshold < 0:
            raise ValueError('imbalance_threshold must be non-negative')

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
        for column in frame.columns:
            if column in OHLCV_COLUMNS or column in {'spread', 'bid_ask_spread', 'quoted_spread', 'bid_size', 'ask_size', 'orderbook_imbalance'}:
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


def generate_intraday_markov_gate(data: pd.DataFrame | str | Path, **kwargs) -> pd.DataFrame:
    """Convenience functional API for intraday Markov regime-gate outputs."""

    return IntradayMarkovRegimeGate(**kwargs).generate(data)


def _find_column(frame: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    by_normalized = {str(column).strip().lower().replace(' ', '_'): column for column in frame.columns}
    for candidate in candidates:
        if candidate in by_normalized:
            return by_normalized[candidate]
    return None
