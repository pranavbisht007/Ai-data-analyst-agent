"""
src/detection/baseline.py
Baseline computation strategies used by the detector.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.analytics.time_series import compute_baseline, ewm_baseline


def rolling_median_baseline(values: pd.Series, window: int = 3) -> pd.Series:
    return compute_baseline(values, window)


def historical_mean_baseline(values: pd.Series, lookback: int = 6) -> pd.Series:
    """Mean of the previous 'lookback' periods, shifted 1 to avoid look-ahead."""
    return values.shift(1).rolling(window=lookback, min_periods=2).mean()


def same_period_baseline(values: pd.Series, period_offset: int = 12) -> pd.Series:
    """Compare to the same period N steps ago (e.g. same month last year)."""
    return values.shift(period_offset)
