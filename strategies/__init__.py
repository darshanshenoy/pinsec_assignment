"""
assignment.strategies
=====================

This package contains all trading strategies implemented for the assignment.

Classes
-------
* :class:`assignment.strategies.base.BaseStrategy` – Abstract base class.
* :class:`assignment.strategies.straddle.StraddleSellerStrategy` – 09:20 short straddle.
* :class:`assignment.strategies.mean_reversion.MeanReversionStrategy` – Bollinger/RSI/EMA mean‑reversion.
"""

from .base import BaseStrategy  # noqa: F401
from .straddle import StraddleSellerStrategy  # noqa: F401
from .mean_reversion import MeanReversionStrategy  # noqa: F401

__all__ = [
    "BaseStrategy",
    "StraddleSellerStrategy",
    "MeanReversionStrategy",
]