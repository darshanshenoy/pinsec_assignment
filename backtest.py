"""
assignment.backtest
===================

This module provides a command line entry point for running backtests on
the strategies defined in :mod:`assignment.strategies`.  It wires
together the data loader, simulator and chosen strategy, iterates over
the minute bars and reports the resulting trade log and PnL.
"""

from __future__ import annotations

import argparse
from typing import Iterable, Optional

from data_loader import MarketDataLoader
from simulator import Simulator
from strategies import StraddleSellerStrategy, MeanReversionStrategy

__all__ = ["run_backtest", "parse_args", "main"]


def run_backtest(
    contract_file: str,
    market_data_file: str,
    strategy_name: str,
    underlying_symbol: str = "NIFTY",
    debug: bool = False,
) -> None:
    """Run a backtest for a single day of data using the chosen strategy."""
    # Load instrument definitions and the historical price data into memory.
    loader = MarketDataLoader(contract_file, market_data_file)
    contract_df = loader.contract_df.copy()
    name_series = contract_df["NameWithSeries"].fillna("")
    # We would like to trade the instrument that best tracks the underlying
    # index, so we rank futures first, then index spot, then ETFs.
    preferred_series = [
        f"{underlying_symbol}-FUTIDX",
        f"{underlying_symbol}-INDEX",
        f"{underlying_symbol}-SPOT",
    ]

    index_token = None
    for series in preferred_series:
        # Pick the first contract in the preferred list that also has market
        # data available in the pickle.
        candidates = contract_df[name_series == series]
        for _, row in candidates.iterrows():
            token = int(row["exchangeInstrumentID"])
            if token in loader.data_by_token:
                index_token = token
                break
        if index_token is not None:
            break

    if index_token is None:
        underlying_rows = contract_df[
            contract_df["Description"].str.startswith(underlying_symbol, na=False)
        ].copy()
        if underlying_rows.empty:
            raise ValueError(f"No instruments found for underlying {underlying_symbol}")
        # Fall back to any other contract that represents the underlying,
        # excluding options because they do not carry their own price series in
        # the market data bundle.
        series_mask = ~name_series.str.contains("OPT", na=False)
        underlying_rows = underlying_rows[series_mask.loc[underlying_rows.index]]
        for _, row in underlying_rows.iterrows():
            token = int(row["exchangeInstrumentID"])
            if token in loader.data_by_token:
                index_token = token
                break

    if index_token is None:
        raise ValueError(f"No market data available for underlying {underlying_symbol}")
    # Instantiate the simulator with initial cash and tie it to the timeline of
    # the chosen instrument.
    sim = Simulator(loader, starting_cash=1_000_000.0, slippage=0.0, debug=debug)
    time_index = loader.data_by_token[index_token].index
    sim.set_time_index(time_index)
    # Dispatch to the concrete strategy requested on the command line.
    if strategy_name.lower() == "straddle":
        strategy = StraddleSellerStrategy(sim, index_token)
    elif strategy_name.lower() == "mean_reversion":
        strategy = MeanReversionStrategy(sim, index_token)
    else:
        raise ValueError("strategy_name must be 'straddle' or 'mean_reversion'")
    # Allow the strategy to prepare any indicators or state before the loop.
    strategy.on_start(0)
    for dt_index in range(len(time_index)):
        # Stop the backtest early if the risk guardrail has been breached.
        if sim.check_max_loss(dt_index):
            sim._log("Max daily loss hit; terminating trading")
            break
        # Pass each time step to the strategy so it can react to new prices.
        strategy.on_bar(dt_index)
    # Give the strategy a final callback to tidy up open positions.
    strategy.on_finish(len(time_index) - 1)
    # Summarise the trades the simulator recorded during the run.
    total_pnl = sum(trade.pnl for trade in sim.trade_log)
    print("Trade log:")
    for trade in sim.trade_log:
        print(
            f"{trade.instrument} | {trade.side} | {trade.entry_time.time()} -> {trade.exit_time.time()} | "
            f"Entry: {trade.entry_price:.2f}, Exit: {trade.exit_price:.2f}, PnL: {trade.pnl:.2f}"
        )
    print(f"\nTotal realised PnL: {total_pnl:.2f}")


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    # argparse builds a friendly command-line interface for the backtester.
    parser = argparse.ArgumentParser(description="Run quant assignment backtest")
    # Path to the static metadata describing each contract.
    parser.add_argument("--contract-file", required=True, help="Path to Contract_File.csv")
    # Path to the pickle containing the minute-by-minute OHLC data.
    parser.add_argument("--market-data-file", required=True, help="Path to One_Day_Data_For_Simulaion.pkl")
    # Choose which trading logic to simulate.
    parser.add_argument("--strategy", required=True, choices=["straddle", "mean_reversion"], help="Strategy to run")
    # Toggle extra print statements inside the simulator and strategies.
    parser.add_argument("--debug", action="store_true", help="Enable verbose logging")
    # Override which underlying symbol to trade (defaults to NIFTY).
    parser.add_argument("--underlying", default="NIFTY", help="Underlying symbol for straddle strategy")
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> None:
    # Parse CLI arguments (or provided list for unit tests) and kick off the run.
    args = parse_args(argv)
    run_backtest(
        contract_file=args.contract_file,
        market_data_file=args.market_data_file,
        strategy_name=args.strategy,
        underlying_symbol=args.underlying,
        debug=args.debug,
    )


if __name__ == "__main__":
    main()
