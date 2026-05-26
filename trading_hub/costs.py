"""Pure cost and slippage helpers for Trading Hub paper-research flows.

Karte B scope only: deterministic arithmetic, no broker/data-source imports,
no order execution, no ledger, and no side effects.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import pandas as pd


def _validate_non_negative(name: str, value: float) -> float:
    value = float(value)
    if value < 0:
        raise ValueError(f"{name} must be non-negative, got {value}")
    return value


def estimate_round_trip_cost_bps(
    fee_bps: float,
    spread_bps: float,
    slippage_bps: float,
    *,
    impact_bps: float = 0.0,
    notional: float = 0.0,
    average_daily_volume: float = 0.0,
    impact_coefficient_bps: float = 0.0,
) -> float:
    """Estimate round-trip trading costs in basis points.

    Conventions:
    - ``fee_bps`` is charged once on entry and once on exit.
    - ``spread_bps`` is the full bid/ask spread cost for the round trip.
    - ``slippage_bps`` is modeled per side, so it is doubled.
    - ``impact_bps`` is an explicit additional round-trip impact add-on.
    - ``impact_coefficient_bps`` optionally adds a quadratic size impact:
      ``impact_coefficient_bps * (notional / average_daily_volume) ** 2``.

    All inputs are scalar, deterministic, and side-effect free.
    """
    fee_bps = _validate_non_negative("fee_bps", fee_bps)
    spread_bps = _validate_non_negative("spread_bps", spread_bps)
    slippage_bps = _validate_non_negative("slippage_bps", slippage_bps)
    impact_bps = _validate_non_negative("impact_bps", impact_bps)
    notional = _validate_non_negative("notional", notional)
    average_daily_volume = _validate_non_negative(
        "average_daily_volume", average_daily_volume
    )
    impact_coefficient_bps = _validate_non_negative(
        "impact_coefficient_bps", impact_coefficient_bps
    )

    size_impact_bps = 0.0
    if impact_coefficient_bps > 0.0:
        # Quadratic impact: (notional/ADV)^2.
        # Almgren-Chriss and Kissel-Glantz often use square-root;
        # we use squaring as a more conservative (larger impact at high participation)
        # research choice. Documented here as an explicit design decision.
        if average_daily_volume <= 0.0:
            raise ValueError(
                "average_daily_volume must be positive when impact_coefficient_bps is used"
            )
        participation_rate = notional / average_daily_volume
        size_impact_bps = impact_coefficient_bps * participation_rate**2

    return (2.0 * fee_bps) + spread_bps + (2.0 * slippage_bps) + impact_bps + size_impact_bps


def apply_cost_to_return(gross_return: float, cost_bps: float) -> float:
    """Subtract basis-point costs from a decimal gross return.

    Example: ``gross_return=0.05`` and ``cost_bps=100`` returns ``0.04``.
    """
    cost_bps = _validate_non_negative("cost_bps", cost_bps)
    return float(gross_return) - (cost_bps / 10_000.0)


def build_slippage_sensitivity_matrix(
    base_params: Mapping[str, Any],
    multipliers: Iterable[float] = (0.5, 1.0, 2.0, 5.0),
) -> pd.DataFrame:
    """Build a deterministic slippage-sensitivity matrix.

    ``base_params`` accepts the keyword arguments of
    :func:`estimate_round_trip_cost_bps` plus optional ``gross_return``.
    Each multiplier scales only ``slippage_bps``. The returned DataFrame has
    one row per scenario with monotonic ``cost_bps`` / ``net_return`` columns
    when multipliers are supplied in ascending order.
    """
    params = dict(base_params)
    gross_return = float(params.pop("gross_return", 0.0))
    base_slippage_bps = _validate_non_negative(
        "slippage_bps", params.get("slippage_bps", 0.0)
    )

    rows: list[dict[str, float]] = []
    for multiplier in multipliers:
        multiplier = float(multiplier)
        if multiplier <= 0.0:
            raise ValueError(f"multiplier must be positive, got {multiplier}")

        scenario_params = dict(params)
        scenario_slippage_bps = base_slippage_bps * multiplier
        scenario_params["slippage_bps"] = scenario_slippage_bps
        cost_bps = estimate_round_trip_cost_bps(**scenario_params)
        rows.append(
            {
                "multiplier": multiplier,
                "slippage_bps": scenario_slippage_bps,
                "cost_bps": cost_bps,
                "net_return": apply_cost_to_return(gross_return, cost_bps),
            }
        )

    return pd.DataFrame(rows, columns=["multiplier", "slippage_bps", "cost_bps", "net_return"])
