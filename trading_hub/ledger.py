"""Isolated ledger / position-tracking module for Trading Hub paper-research flows.

Karte C scope: pure in-memory book-keeping. No broker imports, no network,
no order execution, no backtest runner, no strategy integration, no reporting.

Public API
----------
open_position(ticker, side, entry_price, size, entry_time, cost_bps) -> position_id
close_position(position_id, exit_price, exit_time) -> pnl_bps
get_open_positions() -> list[Position]
get_position_history() -> list[Position]
compute_aggregate_pnl() -> AggregatePnL

The module delegates cost arithmetic to ``apply_cost_to_return`` from Card B
(``trading_hub.costs``).  PnL is expressed in basis points (bps).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Literal

from trading_hub.costs import apply_cost_to_return


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class PositionSide(Enum):
    LONG = "long"
    SHORT = "short"


@dataclass(frozen=True, slots=True)
class Position:
    """Immutable snapshot of a position at any point in its lifetime."""

    position_id: str
    ticker: str
    side: PositionSide
    entry_price: float
    size: float
    entry_time: datetime
    cost_bps: float
    # None means the position is still open
    exit_price: float | None = None
    exit_time: datetime | None = None
    # pnl_bps is set once the position is closed; None while open
    pnl_bps: float | None = None

    @property
    def is_open(self) -> bool:
        return self.exit_time is None

    @property
    def is_closed(self) -> bool:
        return not self.is_open


@dataclass(frozen=True, slots=True)
class AggregatePnL:
    """Aggregated PnL metrics over a collection of (closed) positions."""

    total_pnl_bps: float
    win_rate: float
    avg_win_bps: float
    avg_loss_bps: float
    max_drawdown_bps: float
    trade_count: int


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_positions: dict[str, Position] = {}
_position_counter: int = 0


def _next_id() -> str:
    global _position_counter
    _position_counter += 1
    return f"pos-{_position_counter:06d}"


def _validate_positive(name: str, value: float) -> float:
    value = float(value)
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")
    return value


def _validate_non_negative(name: str, value: float) -> float:
    value = float(value)
    if value < 0:
        raise ValueError(f"{name} must be non-negative, got {value}")
    return value


def _cumulative_max(values: list[float]) -> list[float]:
    """Running maximum."""
    if not values:
        return []
    result = [values[0]]
    for v in values[1:]:
        result.append(max(result[-1], v))
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def open_position(
    ticker: str,
    side: Literal["long", "short"],
    entry_price: float,
    size: float,
    entry_time: datetime,
    cost_bps: float,
) -> str:
    """Open a new position and return its position_id.

    Raises
    ------
    ValueError
        When ``entry_price``, ``size``, or ``cost_bps`` are not positive,
        or when ``side`` is not ``"long"`` / ``"short"``.
    """
    if side not in ("long", "short"):
        raise ValueError(f"side must be 'long' or 'short', got {side!r}")
    _validate_positive("entry_price", entry_price)
    _validate_positive("size", size)
    _validate_non_negative("cost_bps", cost_bps)

    pos_id = _next_id()
    pos = Position(
        position_id=pos_id,
        ticker=str(ticker),
        side=PositionSide(side),
        entry_price=entry_price,
        size=size,
        entry_time=entry_time,
        cost_bps=cost_bps,
    )
    _positions[pos_id] = pos
    return pos_id


def close_position(position_id: str, exit_price: float, exit_time: datetime) -> float:
    """Close a position identified by ``position_id`` and return its PnL in bps.

    The gross return is computed from the side-aware price delta, then costs are
    subtracted via ``apply_cost_to_return`` (Card B).

    Raises
    ------
    ValueError
        When ``position_id`` is unknown, the position is already closed,
        ``exit_price`` is not positive, or ``exit_time`` predates ``entry_time``.
    """
    if position_id not in _positions:
        raise ValueError(f"unknown position_id: {position_id!r}")

    pos = _positions[position_id]

    if pos.is_closed:
        raise ValueError(f"position {position_id!r} is already closed")

    exit_price = _validate_positive("exit_price", exit_price)

    if exit_time < pos.entry_time:
        raise ValueError(
            f"exit_time ({exit_time}) must not be earlier than "
            f"entry_time ({pos.entry_time})"
        )

    # Side-aware gross return
    if pos.side is PositionSide.LONG:
        gross_return = (exit_price - pos.entry_price) / pos.entry_price
    else:  # SHORT
        gross_return = (pos.entry_price - exit_price) / pos.entry_price

    # Apply round-trip costs (entry + exit encoded in cost_bps already)
    net_return = apply_cost_to_return(gross_return, pos.cost_bps)

    # Express net result as bps of entry notional
    pnl_bps = net_return * 10_000.0

    closed_pos = Position(
        position_id=pos.position_id,
        ticker=pos.ticker,
        side=pos.side,
        entry_price=pos.entry_price,
        size=pos.size,
        entry_time=pos.entry_time,
        cost_bps=pos.cost_bps,
        exit_price=exit_price,
        exit_time=exit_time,
        pnl_bps=pnl_bps,
    )
    _positions[position_id] = closed_pos
    return pnl_bps


def is_position_open(position_id: str) -> bool:
    """Return True iff ``position_id`` exists and the position is still open.

    Returns False for unknown ids and for closed positions.
    """
    pos = _positions.get(position_id)
    return pos is not None and pos.is_open


def get_open_positions() -> list[Position]:
    """Return all currently open positions, oldest-first."""
    open_pos = [p for p in _positions.values() if p.is_open]
    open_pos.sort(key=lambda p: p.entry_time)
    return open_pos


def get_position_history() -> list[Position]:
    """Return all positions (open and closed), ordered by entry_time."""
    all_pos = list(_positions.values())
    all_pos.sort(key=lambda p: p.entry_time)
    return all_pos


def compute_aggregate_pnl() -> AggregatePnL:
    """Compute aggregated PnL metrics over all closed positions.

    Metrics
    -------
    total_pnl_bps   : sum of all pnl_bps values
    win_rate        : fraction of trades with pnl_bps > 0
    avg_win_bps     : mean pnl_bps over winning trades (0 if no winners)
    avg_loss_bps    : mean pnl_bps over losing trades (0 if no losers)
    max_drawdown_bps: maximum peak-to-trough decline in cumulative pnl_bps
    trade_count     : number of closed positions

    Returns
    -------
    AggregatePnL
    """
    closed = [p for p in _positions.values() if p.is_closed]

    trade_count = len(closed)
    if trade_count == 0:
        return AggregatePnL(
            total_pnl_bps=0.0,
            win_rate=0.0,
            avg_win_bps=0.0,
            avg_loss_bps=0.0,
            max_drawdown_bps=0.0,
            trade_count=0,
        )

    pnls: list[float] = [float(p.pnl_bps) for p in closed]  # type: ignore[arg-type]

    total_pnl_bps = sum(pnls)
    winners = [p for p in pnls if p > 0]
    losers = [p for p in pnls if p < 0]

    win_rate = len(winners) / trade_count
    avg_win_bps = sum(winners) / len(winners) if winners else 0.0
    avg_loss_bps = sum(losers) / len(losers) if losers else 0.0

    # Equity-curve drawdown: running sum of trade pnls, then peak - equity.
    equity: list[float] = []
    running = 0.0
    for pnl in pnls:
        running += pnl
        equity.append(running)
    peaks = _cumulative_max(equity)
    drawdowns = [peak - eq for peak, eq in zip(peaks, equity)]
    max_drawdown_bps = max(drawdowns) if drawdowns else 0.0

    return AggregatePnL(
        total_pnl_bps=total_pnl_bps,
        win_rate=win_rate,
        avg_win_bps=avg_win_bps,
        avg_loss_bps=avg_loss_bps,
        max_drawdown_bps=max_drawdown_bps,
        trade_count=trade_count,
    )


def reset_ledger() -> None:
    """Clear all positions. Exposed for testing only — not part of the public API."""
    global _positions, _position_counter
    _positions = {}
    _position_counter = 0