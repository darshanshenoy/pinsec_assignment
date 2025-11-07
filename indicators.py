"""
indicators
=====================

This module defines a collection of static helper functions for computing
technical indicators used by the trading strategies.  Separating these
functions into their own module promotes reuse across multiple strategies
and makes unit testing straightforward.

Indicators provided:

* :func:'ema'-  Exponential moving average.
* :func:'rsi'-  Relative Strength Index (RSI).
* :func:'bollinger_bands'-  Bollinger Bands (20 period by default).
* :func:'nearest_strike'-  Round a price to the nearest strike step.
"""

from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd

__all__ = ["ema", "rsi", "bollinger_bands", "nearest_strike"]


def ema(series: pd.Series, period: int) -> pd.Series:
    """Return the exponential moving average of the input series.

    The EMA applies weighting factors that decrease exponentially with
    time.  It reacts more quickly to recent price changes than a simple
    moving average.

    Parameters
    ----------
    series : pandas.Series
        Series of values to smooth.
    period : int
        Lookback period.

    Returns
    -------
    pandas.Series
        Exponentially weighted moving average.
    """
    # pandas.ewm applies the exponential weighting so we simply call it here.
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Compute the Relative Strength Index (RSI).

    The RSI is a momentum oscillator measured on a scale of 0-100.  A
    14-period lookback with thresholds at 70 and 30 is common.

    Parameters
    ----------
    series : pandas.Series
        Series of closing prices.
    period : int, optional
        Number of periods for RSI calculation, default 14.

    Returns
    -------
    pandas.Series
        RSI values corresponding to 'series'.
    """
    delta = series.diff()
    # Positive price moves (gains). Negative values become zero.
    up = delta.clip(lower=0)
    # Negative price moves (losses) – flip the sign to make them positive numbers.
    down = -delta.clip(upper=0)
    # Smooth the gains and losses with an exponential moving average.
    roll_up = up.ewm(alpha=1 / period, adjust=False).mean()
    roll_down = down.ewm(alpha=1 / period, adjust=False).mean()
    # Relative strength compares the size of the average gain to the average loss.
    rs = roll_up / roll_down
    # Convert relative strength into the 0-100 RSI oscillation.
    return 100 - (100 / (1 + rs))


def bollinger_bands(
    series: pd.Series, window: int = 20, num_std: float = 2.0
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate Bollinger Bands for a price series.

    Bollinger Bands consist of a moving average and bands offset by a
    multiple of the standard deviation.  Typical values are a
    20-period window and 2 standard deviations.

    Parameters
    ----------
    series : pandas.Series
        Input series of prices.
    window : int, optional
        Lookback window length for mean and standard deviation, default 20.
    num_std : float, optional
        Number of standard deviations for the bands, default 2.0.

    Returns
    -------
    Tuple[pd.Series, pd.Series, pd.Series]
        Middle, upper and lower Bollinger bands.
    """
    rolling_mean = series.rolling(window).mean()
    # Standard deviation captures how volatile the series is within the window.
    rolling_std = series.rolling(window).std()
    # Upper/lower bands sit above/below the moving average by a set deviation.
    upper_band = rolling_mean + num_std * rolling_std
    lower_band = rolling_mean - num_std * rolling_std
    return rolling_mean, upper_band, lower_band


def nearest_strike(price: float, step: int = 50) -> int:
    """Round a price to the nearest strike increment.

    Indian index options typically trade in 50-point increments.  This helper
    rounds an arbitrary price to the nearest multiple of step.

    Parameters
    ----------
    price : float
        Underlying price to round.
    step : int, optional
        Strike step size, default 50.

    Returns
    -------
    int
        Nearest strike price.
    """
    # Round to the nearest multiple of the strike step (e.g. 50 points).
    return int(round(price / step) * step)
