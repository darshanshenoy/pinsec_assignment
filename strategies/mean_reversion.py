"""
assignment.strategies.mean_reversion
====================================

Implements a mean‑reversion strategy based on Bollinger Bands, RSI and
EMA.  It trades a single symbol (Nifty spot/futures) on one‑minute
bars.

* Long entries occur when price touches the lower Bollinger band, RSI
  < 30 and price > EMA.
* Short entries occur when price touches the upper Bollinger band, RSI
  > 70 and price < EMA.
* Exits occur when price crosses the EMA back or RSI returns to 50.
* All positions are closed at 15:15.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from indicators import ema, bollinger_bands, rsi
from simulator import Simulator
from .base import BaseStrategy

__all__ = ["MeanReversionStrategy"]


class MeanReversionStrategy(BaseStrategy):
    """Mean reversion trading strategy using Bollinger Bands, RSI and EMA."""

    def __init__(self, simulator: Simulator, symbol_token: int) -> None:
        super().__init__(simulator)
        self.token = symbol_token
        # These Series are populated during on_start so we can reuse the values
        # on every bar without recomputing them.
        self.ema_series: pd.Series = pd.Series(dtype=float)
        self.middle_band: pd.Series = pd.Series(dtype=float)
        self.upper_band: pd.Series = pd.Series(dtype=float)
        self.lower_band: pd.Series = pd.Series(dtype=float)
        self.rsi_series: pd.Series = pd.Series(dtype=float)
        # Track whether we currently hold a LONG/SHORT position.
        self.in_position: str | None = None
        # Remember entry details for logging or debugging purposes.
        self.entry_index: int | None = None
        self.entry_price: float | None = None

    def on_start(self, dt_index: int) -> None:
        df = self.simulator.market_data[self.token]
        close = df["Close"]
        # Pre-compute the EMA and Bollinger bands so per-bar work stays light.
        self.ema_series = ema(close, period=20)
        self.middle_band, self.upper_band, self.lower_band = bollinger_bands(
            close, window=20, num_std=2.0
        )
        # RSI is also pre-computed across the whole series once up-front.
        self.rsi_series = rsi(close, period=14)

    def on_bar(self, dt_index: int) -> None:
        ts = self.simulator.time_index[dt_index]
        price = self.simulator.get_market_price(self.token, dt_index)
        if np.isnan(price):
            return
        # Guard against accessing Series indexes that are still warming up.
        ema_val = self.ema_series.iloc[dt_index] if dt_index < len(self.ema_series) else np.nan
        upper = self.upper_band.iloc[dt_index] if dt_index < len(self.upper_band) else np.nan
        lower = self.lower_band.iloc[dt_index] if dt_index < len(self.lower_band) else np.nan
        rsi_val = self.rsi_series.iloc[dt_index] if dt_index < len(self.rsi_series) else np.nan
        if any(np.isnan(x) for x in [ema_val, upper, lower, rsi_val]):
            return
        if self.in_position is None:
            # LONG setup: price flushes to lower band, momentum oversold, but
            # still above the EMA (trend filter).
            if price <= lower and rsi_val < 30 and price > ema_val:
                symbol = self.simulator.data_loader.get_symbol_from_token(self.token) or str(self.token)
                self.simulator.place_order(self.token, symbol, "BUY", 1, dt_index)
                self.in_position = "LONG"
                self.entry_index = dt_index
                self.entry_price = price
                self.simulator._log(
                    f"{ts.strftime('%H:%M')} Enter LONG at {price:.2f}, RSI {rsi_val:.2f}"
                )
            # SHORT setup mirrors the long logic on the upper band.
            elif price >= upper and rsi_val > 70 and price < ema_val:
                symbol = self.simulator.data_loader.get_symbol_from_token(self.token) or str(self.token)
                self.simulator.place_order(self.token, symbol, "SELL", 1, dt_index)
                self.in_position = "SHORT"
                self.entry_index = dt_index
                self.entry_price = price
                self.simulator._log(
                    f"{ts.strftime('%H:%M')} Enter SHORT at {price:.2f}, RSI {rsi_val:.2f}"
                )
        else:
            pos = self.simulator.positions.get(self.token)
            if pos is None:
                # The simulator may have closed the trade for us; reset state.
                self.in_position = None
                return
            # Exit rules: cross back over the EMA or momentum mean-reverts.
            if self.in_position == "LONG" and (price < ema_val or rsi_val >= 50):
                symbol = self.simulator.data_loader.get_symbol_from_token(self.token) or str(self.token)
                self.simulator.place_order(self.token, symbol, "SELL", pos.quantity, dt_index)
                self.simulator._log(
                    f"{ts.strftime('%H:%M')} Exit LONG at {price:.2f}, RSI {rsi_val:.2f}"
                )
                self.in_position = None
                self.entry_index = None
                self.entry_price = None
            elif self.in_position == "SHORT" and (price > ema_val or rsi_val <= 50):
                symbol = self.simulator.data_loader.get_symbol_from_token(self.token) or str(self.token)
                self.simulator.place_order(self.token, symbol, "BUY", pos.quantity, dt_index)
                self.simulator._log(
                    f"{ts.strftime('%H:%M')} Exit SHORT at {price:.2f}, RSI {rsi_val:.2f}"
                )
                self.in_position = None
                self.entry_index = None
                self.entry_price = None
        # Square off at 15:15
        if ts.time() == dt.time(15, 15) and self.in_position is not None:
            pos = self.simulator.positions.get(self.token)
            if pos is not None:
                side = "SELL" if pos.side == "LONG" else "BUY"
                symbol = self.simulator.data_loader.get_symbol_from_token(self.token) or str(self.token)
                self.simulator.place_order(self.token, symbol, side, pos.quantity, dt_index)
                self.simulator._log(
                    f"{ts.strftime('%H:%M')} Square off {pos.side} position at market close"
                )
            self.in_position = None

    def on_finish(self, dt_index: int) -> None:
        # Final safety net to ensure the account has no open trades.
        self.simulator.square_off_all(dt_index)
        self.in_position = None
        self.entry_index = None
        self.entry_price = None
