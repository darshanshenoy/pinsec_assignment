
## Project Structure

- `backtest.py` – Command-line entry point that wires everything together.
- `data_loader.py` – Reads the contract CSV and OHLC pickle into pandas DataFrames.
- `simulator.py` – Event-driven broker simulator that places orders and tracks PnL.
- `models.py` – Lightweight data classes for orders, positions, and trade logs.
- `indicators.py` – Helper functions for EMA, RSI, Bollinger Bands, and strike rounding.
- `strategies/` – Package containing `BaseStrategy`, the short-straddle strategy, and the mean-reversion strategy.
- `data/` – Sample inputs supplied with the assignment (contracts CSV and one-day market data pickle).
- `logs/` – Created automatically after a run to store trade-by-trade CSV reports.

## Installing Dependencies

Create or activate the provided virtual environment and install requirements (pandas, numpy, etc.) if needed:

```bash
source venv/bin/activate
```

If you do not have a requirements file, install the basics manually:

```bash
pip install pandas numpy
```

## Running a Backtest

The project exposes a single command-line entry point:

```bash
python -m backtest \
  --contract-file data/Contract_File.csv \
  --market-data-file data/One_Day_Data_For_Simulaion.pkl \
  --strategy straddle \
  --max-daily-loss 100000 \
  --debug
```

- `--strategy` accepts `straddle` or `mean_reversion`.
- `--debug` is optional; when supplied it prints detailed logs.
- `--underlying` defaults to `NIFTY`, but you can pass another symbol if your contract file has it.
- `--max-daily-loss` (optional) stops trading once the realised + unrealised loss exceeds the specified amount.
- After each run a CSV report is saved under `logs/` containing every trade plus the day’s peak margin usage.

> **Margin model:** the simulator reserves margin equal to 15% of trade notional (`abs(price) * quantity`). Adjust the `margin_rate` parameter in `Simulator` if your interviewer specifies a different haircut.

## End-to-End Flow

1. **Argument parsing (`backtest.parse_args`)**  
   Collects file paths and strategy choices from the command line.
2. **Data loading (`MarketDataLoader`)**  
   Reads `Contract_File.csv` into a metadata DataFrame and unpacks the OHLC pickle into one DataFrame per token.
3. **Instrument discovery (`backtest.run_backtest`)**  
   Chooses an underlying token (prefers futures/spot) that actually has price data in the pickle.
4. **Simulator setup (`Simulator`)**  
   Initializes account cash, positions, and timestamps so every order uses the correct minute.
5. **Strategy selection (`strategies`)**  
   Creates either the short-straddle strategy or the mean-reversion strategy and gives it a reference to the simulator.
6. **Main loop**  
   Iterates through each minute. For every bar, the simulator checks risk limits and then calls `strategy.on_bar(...)`.
7. **Order handling (`Simulator.place_order`)**  
   Fills market orders at the latest price, updates cash, positions, and logs.
8. **Risk & margin tracking (`Simulator`)**  
   Updates notional-based margin usage on every fill and enforces the optional max-loss guardrail.
9. **Completion (`strategy.on_finish` and reporting)**  
   Ensures all trades are closed, prints a trade summary, and writes the CSV report mentioned above.

## Strategy Flows

### Short Straddle (`StraddleSellerStrategy`)

1. At 09:20 the strategy fetches the current index price and rounds it to the nearest strike.
2. It looks up the matching call (CE) and put (PE) instrument tokens using `MarketDataLoader.find_option_token`.
3. Places two SELL orders (one lot each) to create a short straddle and records the combined premium.
4. On every subsequent bar it recomputes total PnL for both legs.  
   - If PnL ≤ -25% of the premium or ≥ +50%, it squares off both legs.  
5. At 15:10 it squares off any remaining open positions as a safety net.
6. `on_finish` runs at the very end to guarantee nothing is left open.

### Mean Reversion (`MeanReversionStrategy`)

1. When the backtest starts, the strategy pre-computes EMA, Bollinger Bands, and RSI for the entire price series.
2. On each bar it fetches the current price, EMA, bands, and RSI value.  
   - Enters **LONG** if price touches the lower band, RSI < 30, and price is still above the EMA.  
   - Enters **SHORT** if price touches the upper band, RSI > 70, and price is below the EMA.
3. If already in a position, it exits when price crosses back over the EMA or RSI reverts to 50.
4. At 15:15 it closes any open trade to avoid holding overnight risk.
5. `on_finish` calls `simulator.square_off_all(...)` for a final cleanup pass.

## Adding Your Own Strategy

1. Create a new file in `strategies/` and subclass `BaseStrategy`.
2. Implement `on_start`, `on_bar`, and `on_finish`.  
   Use `self.simulator.place_order(...)`, `self.simulator.get_market_price(...)`, and other helper methods as shown in the existing strategies.
3. Import your new class in `strategies/__init__.py`.
4. Update `backtest.py` so the `--strategy` flag recognises the new option.

## Troubleshooting Tips

- **KeyError: token not found** – The instrument exists in `Contract_File.csv` but is missing from the pickle. Double-check that the chosen underlying token has market data (`token in loader.data_by_token`).
- **ModuleNotFoundError** – Ensure you are running inside the virtual environment or that dependencies (pandas, numpy) are installed.
- **No trades printed** – Enable `--debug` to see if the strategy skipped entry due to missing indicators or price NaNs.
