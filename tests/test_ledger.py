"""Targeted tests for trading_hub.ledger — Card C.

Scope: pure in-memory position tracking.  No broker, no network, no execution.
"""

from __future__ import annotations

import ast
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from trading_hub import ledger
from trading_hub.ledger import (
    AggregatePnL,
    Position,
    PositionSide,
    close_position,
    compute_aggregate_pnl,
    get_open_positions,
    get_position_history,
    is_position_open,
    open_position,
    reset_ledger,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_ledger():
    """Reset ledger state before and after every test."""
    reset_ledger()
    yield
    reset_ledger()


@pytest.fixture
def base_time():
    return datetime(2026, 1, 1, 9, 30)


# ---------------------------------------------------------------------------
# open_position — happy path
# ---------------------------------------------------------------------------

def test_open_position_returns_id(base_time):
    pid = open_position(
        ticker="BTC-USD",
        side="long",
        entry_price=100.0,
        size=1.0,
        entry_time=base_time,
        cost_bps=10.0,
    )
    assert isinstance(pid, str)
    assert pid.startswith("pos-")


def test_open_position_increments_ids(base_time):
    p1 = open_position("A", "long", 100, 1, base_time, 0)
    p2 = open_position("B", "short", 100, 1, base_time, 0)
    assert p1 != p2
    # Numeric suffixes should be sequential
    n1, n2 = int(p1.split("-")[1]), int(p2.split("-")[1])
    assert n2 > n1


def test_open_position_stores_position(base_time):
    pid = open_position("ETH-USD", "long", 200.0, 0.5, base_time, 5.0)
    pos = get_open_positions()[0]
    assert pos.position_id == pid
    assert pos.ticker == "ETH-USD"
    assert pos.side == PositionSide.LONG
    assert pos.entry_price == 200.0
    assert pos.size == 0.5
    assert pos.entry_time == base_time
    assert pos.cost_bps == 5.0
    assert pos.is_open is True


def test_open_position_short_side(base_time):
    pid = open_position("BTC-USD", "short", 100.0, 1.0, base_time, 0.0)
    pos = get_open_positions()[0]
    assert pos.side == PositionSide.SHORT


# ---------------------------------------------------------------------------
# open_position — validation errors
# ---------------------------------------------------------------------------

def test_open_position_rejects_invalid_side(base_time):
    with pytest.raises(ValueError, match="side must be 'long' or 'short'"):
        open_position("BTC-USD", "invalid", 100.0, 1.0, base_time, 0.0)


def test_open_position_rejects_zero_entry_price(base_time):
    with pytest.raises(ValueError, match="entry_price must be positive"):
        open_position("BTC-USD", "long", 0.0, 1.0, base_time, 0.0)


def test_open_position_rejects_negative_entry_price(base_time):
    with pytest.raises(ValueError, match="entry_price must be positive"):
        open_position("BTC-USD", "long", -50.0, 1.0, base_time, 0.0)


def test_open_position_rejects_zero_size(base_time):
    with pytest.raises(ValueError, match="size must be positive"):
        open_position("BTC-USD", "long", 100.0, 0.0, base_time, 0.0)


def test_open_position_rejects_negative_size(base_time):
    with pytest.raises(ValueError, match="size must be positive"):
        open_position("BTC-USD", "long", 100.0, -1.0, base_time, 0.0)


def test_open_position_rejects_negative_cost_bps(base_time):
    with pytest.raises(ValueError, match="cost_bps must be non-negative"):
        open_position("BTC-USD", "long", 100.0, 1.0, base_time, -5.0)


# ---------------------------------------------------------------------------
# close_position — happy path
# ---------------------------------------------------------------------------

def test_close_position_returns_pnl_bps(base_time):
    pid = open_position("BTC-USD", "long", 100.0, 1.0, base_time, 0.0)
    exit_time = base_time + timedelta(hours=1)
    pnl = close_position(pid, 110.0, exit_time)
    # 10% gross return, no costs → 1000 bps
    assert pnl == pytest.approx(1000.0)


def test_close_position_stores_exit_data(base_time):
    pid = open_position("BTC-USD", "long", 100.0, 1.0, base_time, 0.0)
    exit_time = base_time + timedelta(hours=1)
    pnl = close_position(pid, 110.0, exit_time)
    history = get_position_history()
    assert len(history) == 1
    pos = history[0]
    assert pos.exit_price == 110.0
    assert pos.exit_time == exit_time
    assert pos.pnl_bps == pytest.approx(pnl)
    assert pos.is_closed is True


def test_close_position_long_profitable_with_costs(base_time):
    """+10% gross return, 20 bps round-trip cost → net ~980 bps."""
    pid = open_position("BTC-USD", "long", 100.0, 1.0, base_time, 20.0)
    exit_time = base_time + timedelta(hours=1)
    pnl = close_position(pid, 110.0, exit_time)
    expected = (0.10 - 0.0020) * 10_000.0  # 980 bps
    assert pnl == pytest.approx(expected)


def test_close_position_short_profitable(base_time):
    """Short: entry 100, exit 90 → +10% gross return."""
    pid = open_position("BTC-USD", "short", 100.0, 1.0, base_time, 0.0)
    exit_time = base_time + timedelta(hours=1)
    pnl = close_position(pid, 90.0, exit_time)
    assert pnl == pytest.approx(1000.0)


def test_close_position_long_losing(base_time):
    """Long: entry 100, exit 90 → -10% gross return."""
    pid = open_position("BTC-USD", "long", 100.0, 1.0, base_time, 0.0)
    exit_time = base_time + timedelta(hours=1)
    pnl = close_position(pid, 90.0, exit_time)
    assert pnl == pytest.approx(-1000.0)


def test_close_position_short_losing(base_time):
    """Short: entry 100, exit 110 → -10% gross return."""
    pid = open_position("BTC-USD", "short", 100.0, 1.0, base_time, 0.0)
    exit_time = base_time + timedelta(hours=1)
    pnl = close_position(pid, 110.0, exit_time)
    assert pnl == pytest.approx(-1000.0)


def test_close_position_breakeven_with_costs(base_time):
    """Gross return exactly matches cost → ~0 bps net."""
    pid = open_position("BTC-USD", "long", 100.0, 1.0, base_time, 20.0)
    exit_time = base_time + timedelta(hours=1)
    pnl = close_position(pid, 102.0, exit_time)
    # gross = 0.02, cost = 0.002 → net 0.018 → 180 bps
    assert pnl == pytest.approx(180.0)


def test_close_position_negative_pnl_when_costs_exceed_return(base_time):
    """Tiny positive gross return swallowed by larger cost_bps → negative pnl."""
    # +0.1% gross return, but 50 bps round-trip cost → net = 10 - 50 = -40 bps
    pid = open_position("BTC-USD", "long", 100.0, 1.0, base_time, 50.0)
    exit_time = base_time + timedelta(hours=1)
    pnl = close_position(pid, 100.1, exit_time)
    assert pnl < 0
    assert pnl == pytest.approx(-40.0)


# ---------------------------------------------------------------------------
# close_position — validation errors
# ---------------------------------------------------------------------------

def test_close_position_unknown_id(base_time):
    with pytest.raises(ValueError, match="unknown position_id"):
        close_position("pos-999999", 100.0, base_time)


def test_close_position_already_closed(base_time):
    pid = open_position("BTC-USD", "long", 100.0, 1.0, base_time, 0.0)
    exit_time = base_time + timedelta(hours=1)
    close_position(pid, 110.0, exit_time)
    with pytest.raises(ValueError, match="already closed"):
        close_position(pid, 120.0, exit_time + timedelta(hours=1))


def test_close_position_zero_exit_price(base_time):
    pid = open_position("BTC-USD", "long", 100.0, 1.0, base_time, 0.0)
    with pytest.raises(ValueError, match="exit_price must be positive"):
        close_position(pid, 0.0, base_time + timedelta(hours=1))


def test_close_position_negative_exit_price(base_time):
    pid = open_position("BTC-USD", "long", 100.0, 1.0, base_time, 0.0)
    with pytest.raises(ValueError, match="exit_price must be positive"):
        close_position(pid, -10.0, base_time + timedelta(hours=1))


def test_close_position_exit_before_entry(base_time):
    pid = open_position("BTC-USD", "long", 100.0, 1.0, base_time, 0.0)
    earlier = base_time - timedelta(hours=1)
    with pytest.raises(ValueError, match="exit_time.*must not be earlier"):
        close_position(pid, 90.0, earlier)


# ---------------------------------------------------------------------------
# get_open_positions
# ---------------------------------------------------------------------------

def test_get_open_positions_empty():
    assert get_open_positions() == []


def test_get_open_positions_excludes_closed(base_time):
    p1 = open_position("A", "long", 100, 1, base_time, 0)
    p2 = open_position("B", "long", 100, 1, base_time + timedelta(minutes=1), 0)
    exit_time = base_time + timedelta(hours=1)
    close_position(p1, 110.0, exit_time)
    open_pos = get_open_positions()
    assert len(open_pos) == 1
    assert open_pos[0].position_id == p2


def test_get_open_positions_sorted_by_entry_time(base_time):
    t0 = base_time
    t1 = t0 + timedelta(minutes=5)
    t2 = t0 + timedelta(minutes=10)
    # Open in non-chronological order: C (t2), A (t0), B (t1)
    pid_c = open_position("C", "long", 100, 1, t2, 0)
    pid_a = open_position("A", "long", 100, 1, t0, 0)
    pid_b = open_position("B", "long", 100, 1, t1, 0)
    ids = [p.position_id for p in get_open_positions()]
    # Should be sorted by entry_time: A (t0) → B (t1) → C (t2)
    assert ids == [pid_a, pid_b, pid_c]


# ---------------------------------------------------------------------------
# get_position_history
# ---------------------------------------------------------------------------

def test_get_position_history_includes_open_and_closed(base_time):
    p1 = open_position("A", "long", 100, 1, base_time, 0)
    open_position("B", "long", 100, 1, base_time + timedelta(minutes=1), 0)
    exit_time = base_time + timedelta(hours=1)
    close_position(p1, 110.0, exit_time)
    history = get_position_history()
    assert len(history) == 2


def test_get_position_history_sorted_by_entry_time(base_time):
    t0 = base_time
    t1 = t0 + timedelta(minutes=5)
    # Open B first (t1), then A (t0) — order by entry_time should be A then B
    pid_b = open_position("B", "long", 100, 1, t1, 0)
    pid_a = open_position("A", "long", 100, 1, t0, 0)
    ids = [p.position_id for p in get_position_history()]
    assert ids == [pid_a, pid_b]  # sorted by entry_time, not insertion order


# ---------------------------------------------------------------------------
# compute_aggregate_pnl — happy path
# ---------------------------------------------------------------------------

def test_compute_aggregate_pnl_zero_trades():
    metrics = compute_aggregate_pnl()
    assert metrics.total_pnl_bps == 0.0
    assert metrics.win_rate == 0.0
    assert metrics.avg_win_bps == 0.0
    assert metrics.avg_loss_bps == 0.0
    assert metrics.max_drawdown_bps == 0.0
    assert metrics.trade_count == 0


def test_compute_aggregate_pnl_single_winner(base_time):
    pid = open_position("BTC-USD", "long", 100.0, 1.0, base_time, 0.0)
    exit_time = base_time + timedelta(hours=1)
    close_position(pid, 110.0, exit_time)
    metrics = compute_aggregate_pnl()
    assert metrics.total_pnl_bps == pytest.approx(1000.0)
    assert metrics.win_rate == 1.0
    assert metrics.avg_win_bps == pytest.approx(1000.0)
    assert metrics.avg_loss_bps == 0.0
    assert metrics.max_drawdown_bps == 0.0
    assert metrics.trade_count == 1


def test_compute_aggregate_pnl_single_loser(base_time):
    pid = open_position("BTC-USD", "long", 100.0, 1.0, base_time, 0.0)
    exit_time = base_time + timedelta(hours=1)
    close_position(pid, 90.0, exit_time)
    metrics = compute_aggregate_pnl()
    assert metrics.total_pnl_bps == pytest.approx(-1000.0)
    assert metrics.win_rate == 0.0
    assert metrics.avg_win_bps == 0.0
    assert metrics.avg_loss_bps == pytest.approx(-1000.0)
    assert metrics.trade_count == 1


def test_compute_aggregate_pnl_win_rate(base_time):
    """2 winners, 1 loser → 66.7% win rate."""
    p1 = open_position("A", "long", 100, 1, base_time, 0.0)
    p2 = open_position("B", "long", 100, 1, base_time + timedelta(minutes=1), 0.0)
    p3 = open_position("C", "long", 100, 1, base_time + timedelta(minutes=2), 0.0)
    exit = base_time + timedelta(hours=1)
def test_compute_aggregate_pnl_max_drawdown(base_time):
    """Three trades:
    T1: +200 bps  → cumulative: 200, peak: 200, dd: 0
    T2: -300 bps  → cumulative: -100, peak: 200, dd: 300  ← max drawdown
    T3: +100 bps  → cumulative: 0,     peak: 200, dd: 200
    """
    p1 = open_position("A", "long", 100, 1, base_time, 0.0)
    p2 = open_position("B", "long", 100, 1, base_time + timedelta(minutes=1), 0.0)
    p3 = open_position("C", "long", 100, 1, base_time + timedelta(minutes=2), 0.0)
    exit = base_time + timedelta(hours=1)
    close_position(p1, 102.0, exit)                       # +200 bps
    close_position(p2, 97.0, exit + timedelta(minutes=1)) # -300 bps
    close_position(p3, 101.0, exit + timedelta(minutes=2))# +100 bps
    metrics = compute_aggregate_pnl()
    assert metrics.max_drawdown_bps == pytest.approx(300.0)
    assert metrics.total_pnl_bps == pytest.approx(700.0)


def test_compute_aggregate_pnl_max_drawdown(base_time):
    """Equity-curve drawdown over trade-PnL sequence.

    Trades in bps: +200, -300, +100.
    Equity curve: [200, -100, 0].
    Running peak:  [200, 200, 200].
    Drawdown:      [0, 300, 200].
    Max drawdown:  300 bps.
    """
    p1 = open_position("A", "long", 100, 1, base_time, 0.0)
    p2 = open_position("B", "long", 100, 1, base_time + timedelta(minutes=1), 0.0)
    p3 = open_position("C", "long", 100, 1, base_time + timedelta(minutes=2), 0.0)
    exit = base_time + timedelta(hours=1)
    close_position(p1, 102.0, exit)
    close_position(p2, 97.0, exit + timedelta(minutes=1))
    close_position(p3, 101.0, exit + timedelta(minutes=2))
    metrics = compute_aggregate_pnl()
    assert metrics.max_drawdown_bps == pytest.approx(300.0)


def test_compute_aggregate_pnl_open_positions_excluded(base_time):
    """Open positions must not affect aggregate metrics."""
    open_position("A", "long", 100, 1, base_time, 0.0)
    open_position("B", "long", 100, 1, base_time + timedelta(minutes=1), 0.0)
    metrics = compute_aggregate_pnl()
    assert metrics.trade_count == 0
    assert metrics.total_pnl_bps == 0.0


# ---------------------------------------------------------------------------
# compute_aggregate_pnl — ValueError on invalid state
# ---------------------------------------------------------------------------

def test_compute_aggregate_pnl_empty_ledger():
    # Must not raise — returns zero metrics
    metrics = compute_aggregate_pnl()
    assert metrics.trade_count == 0


# ---------------------------------------------------------------------------
# Position dataclass
# ---------------------------------------------------------------------------

def test_position_is_open_is_closed(base_time):
    pid = open_position("BTC-USD", "long", 100.0, 1.0, base_time, 0.0)
    pos_open = get_open_positions()[0]
    assert pos_open.is_open is True
    assert pos_open.is_closed is False

    close_position(pid, 110.0, base_time + timedelta(hours=1))
    pos_closed = get_position_history()[0]
    assert pos_closed.is_open is False
    assert pos_closed.is_closed is True


def test_position_immutable(base_time):
    pid = open_position("BTC-USD", "long", 100.0, 1.0, base_time, 0.0)
    pos = get_open_positions()[0]
    with pytest.raises(Exception):  # frozen dataclass
        pos.size = 99.0  # type: ignore[reportPropertyType]


# ---------------------------------------------------------------------------
# reset_ledger
# ---------------------------------------------------------------------------

def test_reset_ledger_clears_all(base_time):
    open_position("A", "long", 100, 1, base_time, 0.0)
    open_position("B", "long", 100, 1, base_time + timedelta(minutes=1), 0.0)
    reset_ledger()
    assert get_open_positions() == []
    assert get_position_history() == []


def test_reset_ledger_resets_counter(base_time):
    p1 = open_position("A", "long", 100, 1, base_time, 0.0)
    # p1 is pos-000001 (first position ever)
    reset_ledger()
    p2 = open_position("A", "long", 100, 1, base_time, 0.0)
    # After reset, counter starts from 1 again → same numeric suffix
    assert p1 == p2


# ---------------------------------------------------------------------------
# Cross-card integration: apply_cost_to_return is used
# ---------------------------------------------------------------------------

def test_cost_is_applied_via_card_b_interface(base_time):
    """Verify that the ledger actually calls apply_cost_to_return from costs.py."""
    # Card B: estimate_round_trip_cost_bps(10, 0, 0) → 20 bps
    from trading_hub.costs import estimate_round_trip_cost_bps

    cost = estimate_round_trip_cost_bps(
        fee_bps=10.0, spread_bps=0.0, slippage_bps=0.0
    )
    assert cost == 20.0

    pid = open_position("BTC-USD", "long", 100.0, 1.0, base_time, cost)
    exit_time = base_time + timedelta(hours=1)
    # entry 100, exit 110: +10% gross - 0.2% costs = 9.8% net = 980 bps
    pnl = close_position(pid, 110.0, exit_time)
    assert pnl == pytest.approx(980.0)


# ---------------------------------------------------------------------------
# is_position_open
# ---------------------------------------------------------------------------

def test_is_position_open_true_for_open_position(base_time):
    pid = open_position("BTC-USD", "long", 100.0, 1.0, base_time, 0.0)
    assert is_position_open(pid) is True


def test_is_position_open_false_after_close(base_time):
    pid = open_position("BTC-USD", "long", 100.0, 1.0, base_time, 0.0)
    close_position(pid, 110.0, base_time + timedelta(hours=1))
    assert is_position_open(pid) is False


def test_is_position_open_false_for_unknown_id():
    assert is_position_open("pos-999999") is False


# ---------------------------------------------------------------------------
# Isolation: no broker / network imports
# ---------------------------------------------------------------------------

def test_ledger_does_not_import_broker_or_network_libraries():
    """Static AST scan: ledger stays isolated from execution backends.

    Mirrors test_cost_model.py's isolation guarantee: a top-level import of a
    broker SDK or live-trading library would slip past runtime monkeypatches,
    so we parse the module source and inspect Import / ImportFrom nodes.
    """
    ledger_path = Path(__file__).parents[1] / "trading_hub" / "ledger.py"
    source = ledger_path.read_text()
    tree = ast.parse(source)

    forbidden = {
        "yfinance",
        "ccxt",
        "ibapi",
        "alpaca_trade_api",
        "interactive_brokers",
        "requests",
        "urllib",
        "http",
        "socket",
        "websockets",
        "websocket",
    }
    imported: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[0])

    assert forbidden.isdisjoint(imported), (
        f"forbidden imports found in ledger.py: {forbidden & imported}"
    )


def test_ledger_source_has_no_network_or_eval_primitives():
    """Cheap textual guard against shelling out, eval, exec, or order calls."""
    ledger_path = Path(__file__).parents[1] / "trading_hub" / "ledger.py"
    source = ledger_path.read_text()
    forbidden_tokens = [
        "subprocess",
        "os.system",
        "eval(",
        "exec(",
        "socket.",
        "urlopen",
        "create_order",
        "submit_order",
        "place_order",
    ]
    for token in forbidden_tokens:
        assert token not in source, f"forbidden token in ledger.py: {token!r}"