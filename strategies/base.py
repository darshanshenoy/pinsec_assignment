"""
assignment.strategies.base
==========================

Defines an abstract base class for trading strategies.  Strategies
inherit from :class:`BaseStrategy` and implement the `on_start`,
`on_bar` and `on_finish` methods.  This simple interface allows the
backtest runner to treat all strategies uniformly.
"""

from __future__ import annotations

from typing import Optional

from simulator import Simulator

__all__ = ["BaseStrategy"]


class BaseStrategy:
    """Abstract base class for trading strategies."""

    def __init__(self, simulator: Simulator) -> None:
        # Keep a reference to the simulator so derived strategies can place
        # orders and query account state.
        self.simulator = simulator
        # Derived classes may store state here

    def on_start(self, dt_index: int) -> None:
        """Called at the start of the simulation day."""
        pass

    def on_bar(self, dt_index: int) -> None:
        """Called on every bar (e.g., every minute)."""
        raise NotImplementedError

    def on_finish(self, dt_index: int) -> None:
        """Called at the end of the simulation day."""
        pass
