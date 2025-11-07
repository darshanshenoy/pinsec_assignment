# Backtest Infra – Project Overview

This repository is my take-home solution for the Quant Developer assignment. Everything is structured so that interviewers can inspect individual layers (data, simulator, strategies) without wading through one giant script.

## Architecture At A Glance

```
┌────────────┐      ┌────────────┐      ┌───────────────┐
│ data/      │──┐   │ data_loader│──┐   │ strategies/   │
│ • CSV, Pkl │  │   │ • metadata │  │   │ • straddle    │
└────────────┘  │   │ • OHLC     │  │   │ • mean_rev    │
                ▼   └────────────┘  │   └───────┬───────┘
           ┌──────────────┐          ▼          │
           │ simulator.py │ ← models.py → indicators.py
           └──────────────┘          │
                │                    ▼
                └────────── backtest.py ──> logs/
```

- **data_loader.py** – Reads `Contract_File.csv` and `One_Day_Data_For_Simulaion.pkl`, producing a pandas DataFrame per instrument token plus helper lookups for strike/expiry.
- **simulator.py** – Emulates the XTS API: tracks cash, positions, orders, risk limits, and margin (notional-based, 15% haircut by default).
- **models.py** – Dataclasses for `Order`, `Position`, and `TradeLog`, keeping the simulator logic clean.
- **indicators.py** – EMA, RSI, Bollinger Bands, and strike-rounding utilities shared by strategies.
- **strategies/**
  - `straddle.py`: 09:20 ATM short straddle with combined stop/target and 15:10 mandatory exit.
  - `mean_reversion.py`: Bollinger/RSI/EMA intraday strategy that closes by 15:15.
- **backtest.py** – CLI entry point that wires the modules together, enforces optional `--max-daily-loss`, prints a run summary, and drops a CSV report under `logs/`.

## Quick Start

### 1. Set up Python environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt   # or: pip install pandas numpy
```

### 2. Run a backtest

```bash
python -m backtest \
  --contract-file data/Contract_File.csv \
  --market-data-file data/One_Day_Data_For_Simulaion.pkl \
  --strategy straddle \
  --underlying NIFTY \
  --max-daily-loss 100000 \
  --debug
```

Switch `--strategy` to `mean_reversion` to test the other playbook. `--debug` is optional noise; drop it for silent runs. When `--max-daily-loss` is provided, trading halts once realised + unrealised losses exceed that amount.

### 3. Inspect results

- Console output lists each trade with timestamps, entry/exit prices, realised PnL, total day PnL, and peak margin usage.
- A CSV with the same information is saved to `logs/trade_log_<timestamp>.csv`. Each row is ready for Excel/Sheets sharing with reviewers.

## Extending Or Reviewing

- **New strategies**: create another class under `strategies/`, inherit `BaseStrategy`, then register it in `strategies/__init__.py` and `backtest.py`.
- **Margin assumptions**: tweak `margin_rate` in `Simulator` if your interviewer specifies a different haircut.
- **Data**: drop additional contract/market files into `data/` and pass their paths to the CLI flags—no code changes needed.

That’s the whole project: clean layers, no hidden dependencies, and reproducible runs for the hiring team.
