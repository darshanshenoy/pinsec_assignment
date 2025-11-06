"""
assignment package
===================

This package provides a modular and production‑ready implementation of
the quant developer take‑home assignment.  It splits the original single
file into several coherent modules:

* :mod:`assignment.indicators` – Technical indicator utilities.
* :mod:`assignment.models` – Dataclasses for orders, positions and trades.
* :mod:`assignment.data_loader` – Contract and market data loading.
* :mod:`assignment.simulator` – Event‑driven trading simulator.
* :mod:`assignment.strategies` – Package containing base and concrete strategies.

The top‑level entry point for running a backtest is in
``assignment/backtest.py``.  See the README for instructions on how to
execute the backtest with your own data.
"""


"""
python3 -m backtest \
  --contract-file /home/ubuntu/backtest_infra/data/Contract_File.csv \
  --market-data-file /home/ubuntu/backtest_infra/data/One_Day_Data_For_Simulaion.pkl \
  --strategy straddle \
  --debug
"""
