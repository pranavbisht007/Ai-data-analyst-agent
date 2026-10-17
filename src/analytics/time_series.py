"""
src/analytics/time_series.py
Time-series helpers: decomposition, missing-period detection, stationarity check.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def fill_date_gaps(
    df: pd.DataFrame,
    date_col: str,
    freq: str = "MS",
) -> tuple[pd.DataFrame, list[str]]:
    """
    Reindex the DataFrame to fill missing periods with NaN.
    Returns (filled_df, list_of_missing_period_strings).
    """
    work = df.copy()
    work[date_col] = pd.to_datetime(work[date_col], errors="coerce")
    work = work.dropna(subset=[date_col]).set_index(date_col).sort_index()

    full_idx = pd.date_range(work.index.min(), work.index.max(), freq=freq)
    work = work.reindex(full_idx)

    missing = [str(d.date()) for d in full_idx if d not in df[date_col].values]
    work.index.name = date_col
    return work.reset_index(), missing


def detect_missing_periods(
    series_index: pd.DatetimeIndex,
    freq: str = "MS",
) -> list[str]:
    """Return ISO-date strings for gaps in the index."""
    if len(series_index) < 2:
        return []
    full = pd.date_range(series_index.min(), series_index.max(), freq=freq)
    missing = full.difference(series_index)
    return [str(d.date()) for d in missing]


def compute_baseline(values: pd.Series, window: int = 3) -> pd.Series:
    """
    Rolling median baseline.  Baseline at index i is the median of the
    'window' periods *before* i (exclusive), so it doesn't include the
    current period (avoids look-ahead bias).
    """
    return values.shift(1).rolling(window=window, min_periods=1).median()


def ewm_baseline(values: pd.Series, span: int = 3) -> pd.Series:
    """Exponentially weighted moving average baseline (shifted by 1 period)."""
    return values.shift(1).ewm(span=span, adjust=False).mean()
