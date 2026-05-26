"""Targeted tests for trading_hub.ledger — Card C.

Scope: pure in-memory position tracking.  No broker, no network, no execution.
"""

from __future__ import annotations

from datetime import datetime, timedelta

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
    open_position,
    reset_ledger,
)


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
        open_position("BTC-USD", "invalid", 100.0, 1.0, base_time, 0.0)  # type: ignore[arg-type]


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
    pid = open_position("BTC-USD", "long", 100.0, 1.0, base_time, 20.0)
    exit_time = base_time + timedelta(hours=1)
    pnl = close_position(pid, 110.0, exit_time)
    assert pnl == pytest.approx(980.0)


def test_close_position_short_profitable(base_time):
    pid = open_position("BTC-USD", "short", 100.0, 1.0, base_time, 0.0)
    exit_time = base_time + timedelta(hours=1)
    pnl = close_position(pid, 90.0, exit_time)
    assert pnl == pytest.approx(1000.0)


def test_close_position_long_losing(base_time):
    pid = open_position("BTC-USD", "long", 100.0, 1.0, base_time, 0.0)
    exit_time = base_time + timedelta(hours=1)
    pnl = close_position(pid, 90.0, exit_time)
    assert pnl == pytest.approx(-1000.0)


def test_close_position_short_losing(base_time):
    pid = open_position("BTC-USD", "short", 100.0, 1.0, base_time, 0.0)
    exit_time = base_time + timedelta(hours=1)
    pnl = close_position(pid, 110.0, exit_time)
    assert pnl == pytest.approx(-1000.0)


def test_close_position_breakeven_with_costs(base_time):
    pid = open_position("BTC-USD", "long", 100.0, 1.0, base_time, 20.0)
    exit_time = base_time + timedelta(hours=1)
    pnl = close_position(pid, 102.0, exit_time)
    assert pnl == pytest.approx(180.0)


def test_close_position_negative_pnl_when_costs_exceed_return(base_time):
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
    pid_c = open_position("C", "long", 100, 1, t2, 0)
    pid_a = open_position("A", "long", 100, 1, t0, 0)
    pid_b = open_position("B", "long", 100, 1, t1, 0)
    ids = [p.position_id for p in get_open_positions()]
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
    pid_b = open_position("B", "long", 100, 1, t1, 0)
    pid_a = open_position("A", "long", 100, 1, t0, 0)
    ids = [p.position_id for p in get_position_history()]
    assert ids == [pid_a, pid_b]


# ---------------------------------------------------------------------------
# compute_aggregate_pnl
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
    p1 = open_position("A", "long", 100, 1, base_time, 0.0)
    p2 = open_position("B", "long", 100, 1, base_time + timedelta(minutes=1), 0.0)
    p3 = open_position("C", "long", 100, 1, base_time + timedelta(minutes=2), 0.0)
    exit = base_time + timedelta(hours=1)
    close_position(p1, 110.0, exit)
    close_position(p2, 120.0, exit + timedelta(minutes=1))
    close_position(p3, 90.0, exit + timedelta(minutes=2))
    metrics = compute_aggregate_pnl()
    assert metrics.win_rate == pytest.approx(2 / 3)
    assert metrics.trade_count == 3


def test_compute_aggregate_pnl_avg_win_loss(base_time):
    p1 = open_position("A", "long", 100, 1, base_time, 0.0)
    p2 = open_position("B", "long", 100, 1, base_time + timedelta(minutes=1), 0.0)
    p3 = open_position("C", "long", 100, 1, base_time + timedelta(minutes=2), 0.0)
    exit = base_time + timedelta(hours=1)
    close_position(p1, 108.0, exit)
    close_position(p2, 102.0, exit + timedelta(minutes=1))
    close_position(p3, 97.0, exit + timedelta(minutes=2))
    metrics = compute_aggregate_pnl()
    assert metrics.avg_win_bps == pytest.approx(500.0)
    assert metrics.avg_loss_bps == pytest.approx(-300.0)
    assert metrics.total_pnl_bps == pytest.approx(700.0)


def test_compute_aggregate_pnl_max_drawdown(base_time):
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
    open_position("A", "long", 100, 1, base_time, 0.0)
    open_position("B", "long", 100, 1, base_time + timedelta(minutes=1), 0.0)
    metrics = compute_aggregate_pnl()
    assert metrics.trade_count == 0
    assert metrics.total_pnl_bps == 0.0


def test_compute_aggregate_pnl_empty_ledger():
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
    with pytest.raises(Exception):
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
    reset_ledger()
    p2 = open_position("A", "long", 100, 1, base_time, 0.0)
    assert p1 == p2


# ---------------------------------------------------------------------------
# Cross-card integration
# ---------------------------------------------------------------------------

def test_cost_is_applied_via_card_b_interface(base_time):
    from trading_hub.costs import estimate_round_trip_cost_bps
    cost = estimate_round_trip_cost_bps(fee_bps=10.0, spread_bps=0.0, slippage_bps=0.0)
    assert cost == 20.0
    pid = open_position("BTC-USD", "long", 100.0, 1.0, base_time, cost)
    exit_time = base_time + timedelta(hours=1)
    pnl = close_position(pid, 110.0, exit_time)
    assert pnl == pytest.approx(980.0)