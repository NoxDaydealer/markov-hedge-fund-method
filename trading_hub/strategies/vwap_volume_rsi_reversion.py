from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from trading_hub.strategies.intraday_markov_gate import IntradayMarkovRegimeGate
from trading_hub.strategies.vwap_volume_reversion import VWAPVolumeReversionAdapter

MarkovGateMode = Literal['off', 'neutral_only', 'contrarian_ok']


@dataclass(frozen=True)
class VWAPVolumeRSIReversionAdapter(VWAPVolumeReversionAdapter):
    """Research-only Bybit intraday VWAP + Volume + RSI reversion adapter.

    This adapter consumes caller-supplied BTCUSDT/ETHUSDT linear 1m OHLCV from
    the public collector or equivalent local fixtures. It never connects to an
    exchange and emits paper next-bar execution signals only. Shorts are allowed
    only as paper research signals when ``enable_shorts`` is explicitly true.
    """

    markov_gate: MarkovGateMode = 'off'
    markov_lookback: int = 20
    markov_min_train: int = 20

    def generate_signals(self, data: pd.DataFrame | str | Path) -> pd.DataFrame:
        self._validate_research_parameters()
        frame = self._load_ohlcv(data)
        signals = super().generate_signals(frame)
        markov = self._markov_filter(frame)

        blocked = signals['raw_signal'].ne(0) & ~markov['markov_trade_allowed'].astype(bool)
        if blocked.any():
            signals.loc[blocked, 'raw_signal'] = 0
            signals.loc[blocked, 'signal'] = 0
            signals.loc[blocked, 'reason'] = markov.loc[blocked, 'markov_reason']
            shifted = signals['signal'].shift(1, fill_value=0).astype(int)
            signals['execution_signal'] = shifted
            signals['execution_price'] = frame['open'].where(shifted != 0).astype('Float64')
            signals.loc[shifted == 0, ['stop_price', 'target_price']] = pd.NA

        return pd.concat([signals, markov], axis=1)

    @classmethod
    def load_bybit_ohlcv_jsonl(
        cls,
        path: str | Path,
        *,
        symbol: str | None = None,
        confirmed_only: bool = True,
    ) -> pd.DataFrame:
        """Load normalized collector OHLCV JSONL into a DataFrame.

        Expected rows match ``normalize_kline`` from ``bybit_public_collector``:
        symbol, start_ms, interval, open/high/low/close, volume, turnover, and
        confirmed. Only local files are read; no REST/WebSocket calls occur.
        """

        records: list[dict[str, Any]] = []
        wanted_symbol = symbol.upper() if symbol else None
        with Path(path).open('r', encoding='utf-8') as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                row_symbol = str(row.get('symbol', '')).upper()
                if wanted_symbol and row_symbol != wanted_symbol:
                    continue
                if confirmed_only and row.get('confirmed') is False:
                    continue
                records.append(dict(row))

        if not records:
            raise ValueError(f'no usable Bybit OHLCV rows found in {path}')

        frame = pd.DataFrame.from_records(records)
        if 'start_ms' not in frame.columns:
            raise ValueError('Bybit OHLCV JSONL rows must include start_ms')
        starts = pd.to_numeric(frame['start_ms'], errors='coerce')
        median_start = float(starts.dropna().median()) if starts.notna().any() else 0.0
        timestamp_unit = 's' if median_start < 10_000_000_000 else 'ms'
        frame['timestamp'] = pd.to_datetime(starts, unit=timestamp_unit, errors='coerce')
        frame = frame.dropna(subset=['timestamp']).set_index('timestamp').sort_index()
        frame.index.name = None
        return frame

    def _markov_filter(self, frame: pd.DataFrame) -> pd.DataFrame:
        if self.markov_gate == 'off':
            return pd.DataFrame(
                {
                    'markov_trade_allowed': pd.Series(True, index=frame.index, dtype=bool),
                    'markov_selected_strategy': pd.Series('off', index=frame.index, dtype=object),
                    'markov_mean_reversion_probability': pd.Series(0.0, index=frame.index, dtype=float),
                    'markov_reason': pd.Series('markov_gate_off', index=frame.index, dtype=object),
                },
                index=frame.index,
            )

        gate = IntradayMarkovRegimeGate(lookback=self.markov_lookback, min_train=self.markov_min_train).generate(frame)
        if self.markov_gate == 'neutral_only':
            allowed = gate['selected_strategy'].isin(['mean_reversion', 'flat']) & gate['trade_allowed'].astype(bool)
            reason = pd.Series('markov_neutral_or_mean_reversion_allowed', index=frame.index, dtype=object)
            reason.loc[~allowed] = 'blocked_markov_not_neutral_or_reversion'
        elif self.markov_gate == 'contrarian_ok':
            allowed = gate['selected_strategy'].eq('mean_reversion') & gate['trade_allowed'].astype(bool)
            reason = pd.Series('markov_mean_reversion_allowed', index=frame.index, dtype=object)
            reason.loc[~allowed] = 'blocked_markov_not_mean_reversion'
        else:  # guarded by validation; kept for type checkers
            raise ValueError(f'unsupported markov_gate: {self.markov_gate}')

        return pd.DataFrame(
            {
                'markov_trade_allowed': allowed.astype(bool),
                'markov_selected_strategy': gate['selected_strategy'],
                'markov_mean_reversion_probability': gate['mean_reversion_probability'].astype(float),
                'markov_reason': reason,
            },
            index=frame.index,
        )

    def _validate_research_parameters(self) -> None:
        if self.markov_gate not in {'off', 'neutral_only', 'contrarian_ok'}:
            raise ValueError("markov_gate must be one of 'off', 'neutral_only', 'contrarian_ok'")
        if self.markov_lookback < 2:
            raise ValueError('markov_lookback must be at least 2')
        if self.markov_min_train < 1:
            raise ValueError('markov_min_train must be at least 1')


def generate_vwap_volume_rsi_reversion_signals(data: pd.DataFrame | str | Path, **kwargs: object) -> pd.DataFrame:
    return VWAPVolumeRSIReversionAdapter(**kwargs).generate_signals(data)
