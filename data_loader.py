"""
assignment.data_loader
======================

This module contains the :class:`MarketDataLoader` responsible for reading
contract metadata and minute level OHLC data from disk.  Separating data
loading into its own module keeps the simulator independent from
file format details and eases testing.
"""

from __future__ import annotations

import pickle
from typing import Dict, Optional, Tuple

import pandas as pd

__all__ = ["MarketDataLoader"]


class MarketDataLoader:
    """Utility class to load contract information and OHLC market data."""

    def __init__(self, contract_path: str, market_data_path: str) -> None:
        self.contract_path = contract_path
        self.market_data_path = market_data_path
        # Load metadata and price data immediately so downstream components can
        # start using them without worrying about IO.
        self.contract_df: pd.DataFrame = self._load_contract(contract_path)
        self.data_by_token: Dict[int, pd.DataFrame] = self._load_market_data(
            market_data_path
        )

    @staticmethod
    def _load_contract(path: str) -> pd.DataFrame:
        # Read the CSV file that lists every instrument (futures, options, etc.).
        # low_memory=False makes pandas process the file in one go so dtype
        # inference stays consistent across columns.
        return pd.read_csv(path, low_memory=False)

    def _load_market_data(self, path: str) -> Dict[int, pd.DataFrame]:
        try:
            # Each pickle contains nested dictionaries of OHLC values for every
            # instrument token.  Loading it once here lets the rest of the
            # system work with clean pandas objects.
            with open(path, "rb") as f:
                raw = pickle.load(f)
        except Exception as e:
            raise ValueError(
                f"Failed to load market data from {path}: {e}\n"
                "Ensure the file is a valid pickle containing OHLC data."
            )
        required = {"Open", "High", "Low", "Close"}
        # Bail out early if the pickle does not look like the expected structure.
        if not isinstance(raw, dict) or not required.issubset(raw.keys()):
            raise ValueError(
                "Unexpected market data format: expected a dict with Open/High/Low/Close keys"
            )
        data_by_token: Dict[int, pd.DataFrame] = {}
        # Every key under raw["Close"] represents one instrument token.
        tokens = raw["Close"].keys()
        for token in tokens:
            # Collect Open/High/Low/Close columns separately so they can be
            # merged into a single DataFrame for the token.
            frames = []
            for field in ["Open", "High", "Low", "Close"]:
                # Each field contains a list of dicts with minute/time and price.
                entries = raw[field][token]
                df = pd.DataFrame(entries)
                df["Minute"] = pd.to_datetime(df["Minute"])
                df.set_index("Minute", inplace=True)
                # Rename the generic "Price" column so the DataFrame reads like
                # regular OHLC data.
                df.rename(columns={"Price": field}, inplace=True)
                frames.append(df[[field]])
            # Concatenate the column-wise frames so that each token has one
            # combined DataFrame indexed by minute.
            data_by_token[int(token)] = pd.concat(frames, axis=1).sort_index()
        return data_by_token

    def get_symbol_from_token(self, token: int) -> Optional[str]:
        # Look up the human-readable contract name by instrument token.  This
        # helps strategies print meaningful logs.
        row = self.contract_df[self.contract_df["exchangeInstrumentID"] == token]
        if row.empty:
            return None
        return row.iloc[0]["Description"]

    def find_option_token(
        self, strike: int, option_type: str, trade_date: pd.Timestamp
    ) -> Optional[Tuple[int, str]]:
        """Locate the instrument token for a Nifty option with given strike and type."""
        df = self.contract_df
        # Restrict the contract table to Nifty index options only.
        idx_opts = df[df["NameWithSeries"] == "NIFTY-OPTIDX"].copy()
        # Convert expiry strings (e.g. 2025-10-31T14:30:00) to plain dates for
        # easier comparisons.
        idx_opts["expiry_date"] = pd.to_datetime(idx_opts["ExpiryDatetime"]).dt.date
        # Only consider options that expire on or after the trade date.
        candidates = idx_opts[idx_opts["expiry_date"] >= trade_date.date()]
        if candidates.empty:
            return None
        # Among the valid contracts, choose the one with the nearest expiry.
        nearest = candidates["expiry_date"].min()
        same_expiry = candidates[candidates["expiry_date"] == nearest]
        suffix = f"{strike}{option_type.upper()}"
        # The description ends with the strike + option type (e.g. ...26200CE).
        row = same_expiry[same_expiry["Description"].str.endswith(suffix)]
        if row.empty:
            return None
        token = int(row.iloc[0]["exchangeInstrumentID"])
        description = row.iloc[0]["Description"]
        return token, description
