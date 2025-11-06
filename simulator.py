"""
assignment.simulator
====================

This module implements a simple event‑driven trading simulator.  It
mimics key behaviours of a broker/exchange API: retrieving market data,
placing orders, tracking positions and calculating PnL.  The simulator
uses data loaded by :class:`assignment.data_loader.MarketDataLoader` and
models defined in :mod:`assignment.models`.
"""

from __future__ import annotations

import datetime as dt
from typing import Dict, List, Optional

import numpy as np

from data_loader import MarketDataLoader
from models import Order, Position, TradeLog

__all__ = ["Simulator"]


class Simulator:
    """Event‑driven simulator for trading strategies."""

    def __init__(
        self,
        data_loader: MarketDataLoader,
        starting_cash: float = 1_000_000.0,
        slippage: float = 0.0,
        max_daily_loss: float = None,
        debug: bool = False,
    ) -> None:
        # Store direct references to the data loader and pre-loaded data so we
        # do not have to hit disk again once the simulator starts.
        self.data_loader = data_loader
        self.market_data = data_loader.data_by_token
        self.contract_df = data_loader.contract_df
        self.starting_cash = starting_cash
        self.cash = starting_cash
        self.slippage = slippage
        self.max_daily_loss = max_daily_loss
        self.debug = debug
        self.order_id_counter = 1
        # Orders, positions and trade log are simple python containers that
        # grow as the backtest progresses.
        self.orders: List[Order] = []
        self.positions: Dict[int, Position] = {}
        self.trade_log: List[TradeLog] = []
        # These keep track of where we are in the day while iterating bars.
        self.time_index: Optional[dt.Index] = None
        self.current_index: Optional[int] = None

    def _log(self, msg: str) -> None:
        # Print debug messages only when the user enables --debug.
        if self.debug:
            print(msg)

    def set_time_index(self, index) -> None:
        # The runner provides a list of timestamps (one per bar).  The simulator
        # keeps it so that order timestamps stay consistent through the session.
        self.time_index = index
        self.current_index = 0

    # Market data API
    def get_market_price(self, token: int, dt_index: int) -> float:
        # Return the last available closing price for the token up to the
        # current minute.
        if token not in self.market_data:
            raise KeyError(f"Token {token} not found in market data")
        if self.time_index is None or dt_index >= len(self.time_index):
            raise IndexError("Time index out of bounds")
        ts = self.time_index[dt_index]
        df = self.market_data[token]
        try:
            price = df.loc[:ts]["Close"].iloc[-1]
        except Exception:
            # If we cannot find a price (e.g. missing data), propagate NaN so
            # the caller can decide how to handle it.
            price = np.nan
        return price

    # Order API
    def place_order(
        self,
        token: int,
        symbol: str,
        side: str,
        quantity: int,
        dt_index: int,
    ) -> Order:
        side = side.upper()
        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be 'BUY' or 'SELL'")
        # Market orders get filled immediately at the latest market price.
        price = self.get_market_price(token, dt_index)
        if np.isnan(price):
            raise ValueError(f"No price available for token {token} at index {dt_index}")
        # Apply simple proportional slippage if configured.
        slip = self.slippage * price
        fill_price = price + slip if side == "BUY" else price - slip
        cost = fill_price * quantity
        # Update cash balance to reflect the trade.
        if side == "BUY":
            self.cash -= cost
        else:
            self.cash += cost
        order = Order(
            order_id=self.order_id_counter,
            token=token,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            executed_price=fill_price,
            timestamp=self.time_index[dt_index],
            filled_time=self.time_index[dt_index],
            status="FILLED",
        )
        self.order_id_counter += 1
        self.orders.append(order)
        pos = self.positions.get(token)
        if pos is None:
            # No existing position?  Create a new one with the trade details.
            new_side = "LONG" if side == "BUY" else "SHORT"
            self.positions[token] = Position(
                token=token,
                symbol=symbol,
                side=new_side,
                quantity=quantity,
                entry_price=fill_price,
                entry_time=self.time_index[dt_index],
            )
        else:
            if pos.side == "LONG":
                if side == "BUY":
                    # Averaging up an existing long position: update quantity and
                    # compute the weighted-average entry price.
                    total_qty = pos.quantity + quantity
                    pos.entry_price = (pos.entry_price * pos.quantity + fill_price * quantity) / total_qty
                    pos.quantity = total_qty
                else:
                    # Selling against a long reduces the position size.  If the
                    # size hits zero we record the trade in the log.
                    pos.quantity -= quantity
                    pnl = (fill_price - pos.entry_price) * quantity
                    pos.realised_pnl += pnl
                    if pos.quantity == 0:
                        pos.exit_price = fill_price
                        pos.exit_time = self.time_index[dt_index]
                        self._record_trade(pos)
                        del self.positions[token]
            else:  # SHORT
                if side == "SELL":
                    # Adding to an existing short position.
                    total_qty = pos.quantity + quantity
                    pos.entry_price = (pos.entry_price * pos.quantity + fill_price * quantity) / total_qty
                    pos.quantity = total_qty
                else:
                    # Buying back against a short position.
                    pos.quantity -= quantity
                    pnl = (pos.entry_price - fill_price) * quantity
                    pos.realised_pnl += pnl
                    if pos.quantity == 0:
                        pos.exit_price = fill_price
                        pos.exit_time = self.time_index[dt_index]
                        self._record_trade(pos)
                        del self.positions[token]
        return order

    def _record_trade(self, pos: Position) -> None:
        if pos.exit_time is None:
            return
        # Copy the finalised position details into the trade log so reports can
        # be generated after the backtest completes.
        trade = TradeLog(
            instrument=pos.symbol,
            side=pos.side,
            entry_time=pos.entry_time,
            exit_time=pos.exit_time,
            entry_price=pos.entry_price,
            exit_price=pos.exit_price,
            quantity=pos.quantity,
            pnl=pos.realised_pnl,
        )
        self.trade_log.append(trade)

    # Position management
    def get_positions(self) -> Dict[int, Position]:
        # Expose the dictionary of open positions so strategies can inspect it.
        return self.positions

    def square_off_all(self, dt_index: int) -> None:
        # Close every open position using market orders at the current bar.
        tokens = list(self.positions.keys())
        for token in tokens:
            pos = self.positions[token]
            if pos.side == "LONG":
                # Close longs by selling the existing quantity.
                self.place_order(token, pos.symbol, "SELL", pos.quantity, dt_index)
            else:
                # Close shorts by buying back the borrowed quantity.
                self.place_order(token, pos.symbol, "BUY", pos.quantity, dt_index)

    def mark_to_market(self, dt_index: int) -> float:
        total = 0.0
        for token, pos in self.positions.items():
            # Use the latest available price to value each position.
            price = self.get_market_price(token, dt_index)
            if not np.isnan(price):
                total += pos.update_pnl(price)
        return total

    def total_equity(self, dt_index: int) -> float:
        # Account equity equals available cash plus unrealised PnL.
        return self.cash + self.mark_to_market(dt_index)

    def check_max_loss(self, dt_index: int) -> bool:
        if self.max_daily_loss is None:
            return False
        equity = self.total_equity(dt_index)
        loss = self.starting_cash - equity
        # True means the loss threshold has been breached and trading should stop.
        return loss >= self.max_daily_loss
