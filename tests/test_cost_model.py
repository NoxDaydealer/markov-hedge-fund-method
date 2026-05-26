"""
Tests für Karte B — isoliertes Cost/Slippage-Modul.

Deterministisch und offline: keine Broker, keine Orders, kein Netzwerk.
"""

import ast
from pathlib import Path

import pandas as pd
import pytest

from trading_hub.costs import (
    apply_cost_to_return,
    build_slippage_sensitivity_matrix,
    estimate_round_trip_cost_bps,
)


def test_round_trip_cost_adds_fee_spread_and_slippage_components():
    """Roundtrip-Kosten addieren Fees pro Seite, Spread einmal, Slippage pro Seite."""
    cost_bps = estimate_round_trip_cost_bps(
        fee_bps=2.0,
        spread_bps=1.5,
        slippage_bps=3.0,
    )

    assert cost_bps == pytest.approx(11.5)  # 2*2 + 1.5 + 2*3


def test_round_trip_cost_includes_direct_impact_bps():
    """Eine explizite Impact-Komponente wird auf die Basis-Kosten addiert."""
    cost_bps = estimate_round_trip_cost_bps(
        fee_bps=1.0,
        spread_bps=2.0,
        slippage_bps=1.5,
        impact_bps=4.0,
    )

    assert cost_bps == pytest.approx(11.0)  # 2*1 + 2 + 2*1.5 + 4


def test_size_based_impact_increases_with_notional_size():
    """Größere Trade-Größe erhöht die modellierte Impact-Komponente."""
    small = estimate_round_trip_cost_bps(
        fee_bps=0.5,
        spread_bps=1.0,
        slippage_bps=1.0,
        notional=10_000,
        average_daily_volume=1_000_000,
        impact_coefficient_bps=100.0,
    )
    large = estimate_round_trip_cost_bps(
        fee_bps=0.5,
        spread_bps=1.0,
        slippage_bps=1.0,
        notional=50_000,
        average_daily_volume=1_000_000,
        impact_coefficient_bps=100.0,
    )

    assert large > small


def test_apply_cost_to_return_subtracts_bps_cost_from_decimal_return():
    """100 bps Kosten reduzieren einen 5%-Brutto-Return auf 4%."""
    net_return = apply_cost_to_return(gross_return=0.05, cost_bps=100.0)

    assert net_return == pytest.approx(0.04)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"fee_bps": -0.1, "spread_bps": 1.0, "slippage_bps": 1.0},
        {"fee_bps": 0.1, "spread_bps": -1.0, "slippage_bps": 1.0},
        {"fee_bps": 0.1, "spread_bps": 1.0, "slippage_bps": -1.0},
        {"fee_bps": 0.1, "spread_bps": 1.0, "slippage_bps": 1.0, "impact_bps": -1.0},
        {"fee_bps": 0.1, "spread_bps": 1.0, "slippage_bps": 1.0, "notional": -1.0},
        {"fee_bps": 0.1, "spread_bps": 1.0, "slippage_bps": 1.0, "average_daily_volume": -1.0},
        {"fee_bps": 0.1, "spread_bps": 1.0, "slippage_bps": 1.0, "impact_coefficient_bps": -1.0},
    ],
)
def test_negative_cost_inputs_raise_value_error(kwargs):
    """Negative Kosten-, Größen- oder Impact-Inputs sind ungültig."""
    with pytest.raises(ValueError):
        estimate_round_trip_cost_bps(**kwargs)


def test_negative_cost_bps_in_apply_cost_to_return_raises_value_error():
    with pytest.raises(ValueError):
        apply_cost_to_return(gross_return=0.01, cost_bps=-1.0)


def test_sensitivity_matrix_is_monotonic_for_costs_and_returns():
    """Höhere Slippage-Multiplikatoren erhöhen Kosten und senken Netto-Returns."""
    matrix = build_slippage_sensitivity_matrix(
        {
            "fee_bps": 1.0,
            "spread_bps": 2.0,
            "slippage_bps": 3.0,
            "impact_bps": 1.0,
            "gross_return": 0.02,
        },
        multipliers=[0.5, 1.0, 2.0, 5.0],
    )

    assert isinstance(matrix, pd.DataFrame)
    assert list(matrix["multiplier"]) == [0.5, 1.0, 2.0, 5.0]
    assert matrix["cost_bps"].is_monotonic_increasing
    assert matrix["net_return"].is_monotonic_decreasing


def test_invalid_sensitivity_multiplier_raises_value_error():
    with pytest.raises(ValueError):
        build_slippage_sensitivity_matrix(
            {"fee_bps": 1.0, "spread_bps": 2.0, "slippage_bps": 3.0},
            multipliers=[1.0, 0.0],
        )


def test_cost_model_does_not_import_broker_or_network_libraries():
    """Das Kostenmodul bleibt isoliert von Broker-/Datenquellen-Bibliotheken.

    Verwendet statischen AST-Scan, da ein nachträglicher Monkeypatch von
    importlib.import_module die transitiven Top-Level-Imports nicht mehr erfasst.
    """
    costs_path = Path(__file__).parents[1] / "trading_hub" / "costs.py"
    source = costs_path.read_text()
    tree = ast.parse(source)

    forbidden = {"yfinance", "ccxt", "ibapi", "alpaca_trade_api", "interactive_brokers"}
    imported: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[0])

    assert forbidden.isdisjoint(imported), f"forbidden imports found: {forbidden & imported}"


def test_notional_without_impact_coefficient_requires_no_adv():
    """notional > 0 aber impact_coefficient_bps == 0: kein ADV erforderlich."""
    # Sollte keinen Fehler auslösen, obwohl notional > 0 und kein ADV gegeben
    cost_bps = estimate_round_trip_cost_bps(
        fee_bps=1.0,
        spread_bps=2.0,
        slippage_bps=1.0,
        notional=50_000,
        impact_coefficient_bps=0.0,
        # kein average_daily_volume — soll nicht crashen
    )
    # Basiskosten ohne size impact: 2*1 + 2 + 2*1 + 0 = 6
    assert cost_bps == pytest.approx(6.0)


def test_impact_cost_decreases_with_larger_adv_at_same_notional():
    """Bei gleichem Notional: groesserer ADV → niedrigere Impact-Kosten (Monotonie in ADV)."""
    small_adv = estimate_round_trip_cost_bps(
        fee_bps=0.5,
        spread_bps=1.0,
        slippage_bps=1.0,
        notional=50_000,
        average_daily_volume=500_000,
        impact_coefficient_bps=100.0,
    )
    large_adv = estimate_round_trip_cost_bps(
        fee_bps=0.5,
        spread_bps=1.0,
        slippage_bps=1.0,
        notional=50_000,
        average_daily_volume=1_000_000,
        impact_coefficient_bps=100.0,
    )

    assert large_adv < small_adv, "groesserer ADV muss kleinere Impact-Kosten ergeben"
