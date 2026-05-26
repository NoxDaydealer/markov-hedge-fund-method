from __future__ import annotations

from collections.abc import Mapping, Sequence
from itertools import product
from typing import Any, Callable

import pandas as pd

from trading_hub.hft_evaluator import EvaluationResult, evaluate_intraday_strategy


ParamGrid = Mapping[str, Sequence[Any]]
AdapterFactory = Callable[..., Any]


def run_param_sweep(
    data: pd.DataFrame,
    adapter_factory: AdapterFactory,
    param_grid: ParamGrid,
    *,
    max_combinations: int = 100,
    signal_column: str = 'signal',
    evaluator_kwargs: Mapping[str, Any] | None = None,
) -> pd.DataFrame:
    """Evaluate a deterministic, compact research-only adapter parameter sweep.

    ``adapter_factory`` is normally a strategy adapter class. Each parameter
    combination is instantiated locally, asked for ``generate_signals(data)``, and
    evaluated only through ``hft_evaluator.evaluate_intraday_strategy``. The
    helper never fetches market data, calls broker APIs, or places orders.
    """

    if max_combinations < 1:
        raise ValueError('max_combinations must be at least 1')
    if not isinstance(param_grid, Mapping):
        raise TypeError('param_grid must be a mapping of parameter names to value sequences')

    combinations = _parameter_combinations(param_grid)
    if len(combinations) > max_combinations:
        raise ValueError(
            f'parameter sweep has {len(combinations)} combinations, exceeding max_combinations={max_combinations}'
        )

    eval_kwargs = dict(evaluator_kwargs or {})
    rows: list[dict[str, Any]] = []
    adapter_name = getattr(adapter_factory, '__name__', adapter_factory.__class__.__name__)
    for combo_id, params in enumerate(combinations):
        adapter = adapter_factory(**params)
        generated = adapter.generate_signals(data)
        if not isinstance(generated, pd.DataFrame):
            raise TypeError('adapter.generate_signals() must return a pandas DataFrame')
        if signal_column not in generated.columns:
            raise ValueError(f"signal column '{signal_column}' not found in generated signals")
        signal = generated.loc[:, signal_column]
        if isinstance(signal, pd.DataFrame):
            raise ValueError(f"signal column '{signal_column}' must identify exactly one generated column")

        evaluation = evaluate_intraday_strategy(
            data,
            signal,
            name=f'{adapter_name}[{combo_id}]',
            **eval_kwargs,
        )
        rows.append(_result_row(evaluation, params))

    return pd.DataFrame.from_records(rows)


def _parameter_combinations(param_grid: ParamGrid) -> list[dict[str, Any]]:
    names = list(param_grid.keys())
    values_by_name: list[list[Any]] = []
    for name in names:
        values = param_grid[name]
        if isinstance(values, (str, bytes)):
            raise TypeError(f"param_grid['{name}'] must be a sequence of values, not a string")
        try:
            value_list = list(values)
        except TypeError as exc:
            raise TypeError(f"param_grid['{name}'] must be an iterable sequence of values") from exc
        if not value_list:
            raise ValueError(f"param_grid['{name}'] must contain at least one value")
        values_by_name.append(value_list)

    return [dict(zip(names, combo, strict=True)) for combo in product(*values_by_name)]


def _result_row(evaluation: EvaluationResult, params: Mapping[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {f'param_{name}': value for name, value in params.items()}
    row['name'] = evaluation.name
    row.update(evaluation.metrics)
    row['evaluation'] = evaluation
    return row
