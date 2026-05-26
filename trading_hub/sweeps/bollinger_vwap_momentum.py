from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from trading_hub.parameter_sweep import ParamGrid, run_param_sweep
from trading_hub.strategies.bollinger_vwap_momentum import BollingerVwapMomentumAdapter
from trading_hub.sweeps._common import _write_optional_csv

BOLLINGER_VWAP_MOMENTUM_COMPACT_GRID: ParamGrid = {
    'bb_period': [10, 20],
    'bb_stddev': [2.0],
    'bandwidth_percentile_window': [20],
    'bandwidth_percentile_threshold': [0.20],
    'volume_window': [10],
    'volume_multiplier': [1.25],
    'rsi_period': [7],
    'rsi_long_threshold': [55.0],
    'rsi_short_threshold': [45.0],
    'macd_fast': [6],
    'macd_slow': [13],
    'macd_signal': [5],
    'atr_period': [7],
    'enable_shorts': [False],
}


def run_bollinger_vwap_momentum_sweep(
    data: pd.DataFrame,
    *,
    param_grid: ParamGrid | None = None,
    output_csv: str | Path | None = None,
    max_combinations: int = 16,
    evaluator_kwargs: Mapping[str, Any] | None = None,
) -> pd.DataFrame:
    """Run a compact, local-only Bollinger/VWAP/momentum parameter sweep.

    This wrapper keeps the default grid deliberately small for smoke tests,
    delegates evaluation to ``run_param_sweep``/``hft_evaluator``, and writes CSV
    output only when ``output_csv`` is explicitly provided.
    """

    grid = param_grid or BOLLINGER_VWAP_MOMENTUM_COMPACT_GRID
    result = run_param_sweep(
        data,
        BollingerVwapMomentumAdapter,
        grid,
        max_combinations=max_combinations,
        evaluator_kwargs=evaluator_kwargs,
    )
    _write_optional_csv(result, output_csv)
    return result
