"""
assignment.strategies.straddle
==============================

Implements the 09:20 AM short straddle on the Nifty index.  The
strategy sells one at‑the‑money call and put at 09:20, using the
nearest weekly/monthly expiry.  A combined premium stop loss (‑25 %) and
target (+50 %) are enforced; all open positions are squared off at
15:10.
"""

from __future__ import annotations

import datetime as dt
from typing import Optional

import numpy as np

from data_loader import MarketDataLoader
from indicators import nearest_strike
from simulator import Simulator
from .base import BaseStrategy

__all__ = ["StraddleSellerStrategy"]


class StraddleSellerStrategy(BaseStrategy):
    """Short straddle strategy that triggers at 09:20."""

    def __init__(self, simulator: Simulator, index_token: int) -> None:
        super().__init__(simulator)
        self.index_token = index_token
        # These attributes track the individual option legs we sell.
        self.call_token: Optional[int] = None
        self.put_token: Optional[int] = None
        self.premium_collected: float = 0.0
        # Flags and timestamps modelling whether we currently hold a straddle.
        self.open_trades: bool = False
        self.trade_date: Optional[dt.date] = None

    def on_start(self, dt_index: int) -> None:
        ts = self.simulator.time_index[dt_index]
        # Cache the trading date so we can request the correct option expiry.
        self.trade_date = ts.date()

    def on_bar(self, dt_index: int) -> None:
        ts = self.simulator.time_index[dt_index]
        # Enter straddle at 09:20
        if ts.time() == dt.time(9, 20) and not self.open_trades:
            # Fetch the latest underlying price to decide which strike is ATM.
            underlying = self.simulator.get_market_price(self.index_token, dt_index)
            if np.isnan(underlying):
                return
            strike = nearest_strike(underlying, step=50)
            loader: MarketDataLoader = self.simulator.data_loader
            # Find the instrument tokens for the call and put that share the
            # same ATM strike and expiry closest to today.
            call_res = loader.find_option_token(strike, "CE", ts)
            put_res = loader.find_option_token(strike, "PE", ts)
            if call_res is None or put_res is None:
                self.simulator._log(
                    f"No options found for strike {strike}, skipping entry"
                )
                return
            self.call_token, call_symbol = call_res
            self.put_token, put_symbol = put_res
            # Sell one lot of both call and put to create the short straddle.
            call_order = self.simulator.place_order(
                self.call_token, call_symbol, "SELL", 1, dt_index
            )
            put_order = self.simulator.place_order(
                self.put_token, put_symbol, "SELL", 1, dt_index
            )
            self.premium_collected = (
                call_order.executed_price + put_order.executed_price
            )
            # Risk controls: total stop loss is -25% of premium, target +50%.
            self.stop_loss = -0.25 * self.premium_collected
            self.target = 0.5 * self.premium_collected
            self.open_trades = True
            self.simulator._log(
                f"Sold straddle at strike {strike}, premium {self.premium_collected:.2f}"
            )
            return
        # Manage exits
        if self.open_trades:
            call_pos = self.simulator.positions.get(self.call_token)
            put_pos = self.simulator.positions.get(self.put_token)
            if call_pos is None or put_pos is None:
                return
            # Pull the latest prices so we can mark the positions to market.
            call_price = self.simulator.get_market_price(self.call_token, dt_index)
            put_price = self.simulator.get_market_price(self.put_token, dt_index)
            call_pnl = call_pos.update_pnl(call_price)
            put_pnl = put_pos.update_pnl(put_price)
            # Combine unrealised and realised PnL from both legs.
            total_pnl = call_pnl + put_pnl + call_pos.realised_pnl + put_pos.realised_pnl
            if total_pnl <= self.stop_loss or total_pnl >= self.target:
                self.simulator._log(
                    f"Closing straddle at {ts.strftime('%H:%M')} with PnL {total_pnl:.2f}"
                )
                self.simulator.square_off_all(dt_index)
                self.open_trades = False
        # End of day square off
        if ts.time() == dt.time(15, 10) and self.open_trades:
            self.simulator._log(
                f"Square off straddle at {ts.strftime('%H:%M')} before market close"
            )
            self.simulator.square_off_all(dt_index)
            self.open_trades = False

    def on_finish(self, dt_index: int) -> None:
        if self.open_trades:
            # Extra safety: ensure nothing remains open after the backtest.
            self.simulator.square_off_all(dt_index)
            self.open_trades = False
