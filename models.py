"""
models
=================

This module defines simple data containers for orders, positions and trade
log entries.  Using `@dataclass` for these structures makes the code more
readable and concise.  They are used throughout the simulator and
strategies to track state.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Optional, Tuple

__all__ = ["Order", "Position", "TradeLog"]


@dataclass
class Order:
    """Represents an order placed through the simulator."""
    # Unique identifier assigned by the simulator.
    order_id: int
    # Numerical token that maps to a contract in Contract_File.csv.
    token: int
    # Human-readable symbol for logging/reporting.
    symbol: str
    # BUY or SELL.
    side: str
    # Number of units transacted.
    quantity: int
    # Market price observed when the order was created.
    price: float
    # Actual fill price after slippage (if any).
    executed_price: Optional[float] = None
    # When the order was submitted.
    timestamp: dt.datetime = field(default_factory=lambda: dt.datetime.now())
    # When the order was filled (immediate for market orders in this sim).
    filled_time: Optional[dt.datetime] = None
    # Status is always FILLED in this simple simulator but kept for realism.
    status: str = "NEW"
    # Placeholder to show how order types could be extended later.
    order_type: str = "MARKET"


@dataclass
class Position:
    """Represents an open position in a single instrument."""
    token: int
    symbol: str
    side: str  # 'LONG' or 'SHORT'
    quantity: int
    entry_price: float
    entry_time: dt.datetime
    # Optional exit rules provided by the strategy.
    stop_loss: Optional[float] = None
    target: Optional[float] = None
    # These values are populated when the position is closed.
    exit_price: Optional[float] = None
    exit_time: Optional[dt.datetime] = None
    # Tracks realised profit or loss from partial exits.
    realised_pnl: float = 0.0
    # Margin reserved for this position (updated by the simulator).
    margin_required: float = 0.0

    def is_open(self) -> bool:
        # A position is still active while we have not recorded an exit time.
        return self.exit_time is None

    def update_pnl(self, current_price: float) -> float:
        """Calculate mark-to-market PnL for this position."""
        if self.side.upper() == "LONG":
            return (current_price - self.entry_price) * self.quantity
        return (self.entry_price - current_price) * self.quantity

    def check_stop_target(self, current_price: float) -> Tuple[bool, bool]:
        """Check whether stop loss or target has been reached."""
        hit_stop = False
        hit_target = False
        if self.stop_loss is None and self.target is None:
            return hit_stop, hit_target
        if self.side.upper() == "LONG":
            if self.stop_loss is not None and current_price <= self.stop_loss:
                hit_stop = True
            if self.target is not None and current_price >= self.target:
                hit_target = True
        else:  # short
            if self.stop_loss is not None and current_price >= self.stop_loss:
                hit_stop = True
            if self.target is not None and current_price <= self.target:
                hit_target = True
        return hit_stop, hit_target


@dataclass
class TradeLog:
    """Record of a completed trade for reporting purposes."""
    # Description and direction of the finished trade.
    instrument: str
    side: str
    # Entry/exit timestamps and prices pulled from the final position state.
    entry_time: dt.datetime
    exit_time: dt.datetime
    entry_price: float
    exit_price: float
    # Number of contracts traded and the realised PnL.
    quantity: int
    pnl: float
