from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from trading_hub.parameter_sweep import ParamGrid, run_param_sweep
from trading_hub.strategies.vwap_volume_rsi_reversion import VWAPVolumeRSIReversionAdapter
from trading_hub.sweeps._common import _write_optional_csv

VWAP_VOLUME_RSI_REVERSION_COMPACT_GRID: ParamGrid = {
    'vwap_window': [20, 40],
    'z_window': [20],
    'rsi_period': [7],
    'stochrsi_period': [7],
    'volume_window': [10],
    'atr_period': [7],
    'z_threshold': [0.75],
    'volume_multiple': [1.25],
    'local_extreme_lookback': [2],
    'enable_shorts': [False],
    'markov_gate': ['off'],
}


def run_vwap_volume_rsi_reversion_sweep(
    data: pd.DataFrame,
    *,
    param_grid: ParamGrid | None = None,
    output_csv: str | Path | None = None,
    max_combinations: int = 16,
    evaluator_kwargs: Mapping[str, Any] | None = None,
) -> pd.DataFrame:
    """Run a compact, local-only VWAP/volume/RSI reversion parameter sweep.

    This is intentionally a smoke-testable wrapper around ``run_param_sweep``:
    caller-supplied OHLCV data is evaluated locally, hft_evaluator metrics are
    returned in the DataFrame, and no CSV is written unless ``output_csv`` is
    provided.
    """

    grid = param_grid or VWAP_VOLUME_RSI_REVERSION_COMPACT_GRID
    result = run_param_sweep(
        data,
        VWAPVolumeRSIReversionAdapter,
        grid,
        max_combinations=max_combinations,
        evaluator_kwargs=evaluator_kwargs,
    )
    _write_optional_csv(result, output_csv)
    return result


# Backwards-compatible shorter alias matching the Claude Ultraplan wording.
run_vwap_rsi_reversion_sweep = run_vwap_volume_rsi_reversion_sweep
