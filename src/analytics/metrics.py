"""
src/analytics/metrics.py
Core KPI calculations.  All functions are pure — they take a Series / DataFrame
and return a scalar or Series.  Division by zero and insufficient history are
handled explicitly.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_SENTINEL = float("nan")


# ── Basic aggregations ────────────────────────────────────────────────────────

def series_sum(s: pd.Series) -> float:
    return float(s.sum()) if not s.empty else _SENTINEL


def series_mean(s: pd.Series) -> float:
    cleaned = pd.to_numeric(s, errors="coerce").dropna()
    return float(cleaned.mean()) if not cleaned.empty else _SENTINEL


def series_median(s: pd.Series) -> float:
    cleaned = pd.to_numeric(s, errors="coerce").dropna()
    return float(cleaned.median()) if not cleaned.empty else _SENTINEL


def series_min(s: pd.Series) -> float:
    cleaned = pd.to_numeric(s, errors="coerce").dropna()
    return float(cleaned.min()) if not cleaned.empty else _SENTINEL


def series_max(s: pd.Series) -> float:
    cleaned = pd.to_numeric(s, errors="coerce").dropna()
    return float(cleaned.max()) if not cleaned.empty else _SENTINEL


def series_count(s: pd.Series) -> int:
    return int(s.notna().sum())


# ── Period-over-period changes ────────────────────────────────────────────────

def absolute_change(current: float, previous: float) -> float:
    if np.isnan(current) or np.isnan(previous):
        return _SENTINEL
    return current - previous


def percentage_change(current: float, previous: float) -> Optional[float]:
    """Return percentage change or None when mathematically undefined."""
    if np.isnan(current) or np.isnan(previous):
        return None
    if previous == 0:
        return None  # division by zero — caller must handle
    return ((current - previous) / abs(previous)) * 100.0


# ── Rolling statistics ────────────────────────────────────────────────────────

def rolling_mean(s: pd.Series, window: int) -> pd.Series:
    return s.rolling(window=window, min_periods=max(1, window // 2)).mean()


def rolling_median(s: pd.Series, window: int) -> pd.Series:
    return s.rolling(window=window, min_periods=max(1, window // 2)).median()


def rolling_std(s: pd.Series, window: int) -> pd.Series:
    return s.rolling(window=window, min_periods=max(2, window // 2)).std()


# ── Trend ─────────────────────────────────────────────────────────────────────

def linear_trend_slope(s: pd.Series) -> Optional[float]:
    """
    Fit a simple OLS line and return the slope per period.
    Returns None if fewer than 3 non-null observations.
    """
    clean = pd.to_numeric(s, errors="coerce").dropna()
    if len(clean) < 3:
        return None
    x = np.arange(len(clean), dtype=float)
    slope = float(np.polyfit(x, clean.values, 1)[0])
    return slope


def rate_of_change(s: pd.Series) -> pd.Series:
    """Period-over-period percentage change, returning NaN where undefined."""
    numeric = pd.to_numeric(s, errors="coerce")
    # Use pct_change but mask division-by-zero (where previous == 0)
    pct = numeric.pct_change() * 100.0
    pct[numeric.shift(1) == 0] = np.nan
    return pct


# ── MAD-based Z-score ─────────────────────────────────────────────────────────

def mad_zscore(s: pd.Series) -> pd.Series:
    """
    Median Absolute Deviation Z-score (robust outlier measure).
    Returns NaN where MAD == 0 (constant series).
    Score > 3 is often considered anomalous.
    """
    numeric = pd.to_numeric(s, errors="coerce")
    med = numeric.median()
    mad = (numeric - med).abs().median()
    if mad == 0:
        return pd.Series(np.zeros(len(s)), index=s.index)
    return (numeric - med).abs() / mad


# ── Aggregation by period ─────────────────────────────────────────────────────

_FREQ_MAP = {
    "daily": "D",
    "weekly": "W-MON",
    "monthly": "MS",
}


def aggregate_by_period(
    df: pd.DataFrame,
    date_col: str,
    value_col: str,
    period: str = "monthly",
    agg: str = "sum",
) -> pd.DataFrame:
    """
    Resample a time-series column to the chosen period.

    Parameters
    ----------
    period : 'daily' | 'weekly' | 'monthly'
    agg    : 'sum' | 'mean' | 'max' | 'min'

    Returns a DataFrame with columns ['period', value_col].
    """
    if period not in _FREQ_MAP:
        raise ValueError(f"period must be one of {list(_FREQ_MAP)}, got '{period}'.")
    if agg not in ("sum", "mean", "max", "min"):
        raise ValueError(f"agg must be sum/mean/max/min, got '{agg}'.")

    work = df[[date_col, value_col]].copy()
    work[date_col] = pd.to_datetime(work[date_col], errors="coerce")
    work = work.dropna(subset=[date_col])
    work[value_col] = pd.to_numeric(work[value_col], errors="coerce")
    work = work.set_index(date_col).sort_index()

    freq = _FREQ_MAP[period]
    resampled = work[value_col].resample(freq).agg(agg)
    result = resampled.reset_index()
    result.columns = ["period", value_col]
    return result


def detect_interval(df: pd.DataFrame, date_col: str) -> str:
    """
    Heuristic: infer the most common gap between consecutive dates.
    Returns 'daily', 'weekly', or 'monthly'.
    """
    dates = pd.to_datetime(df[date_col], errors="coerce").dropna().sort_values()
    if len(dates) < 2:
        return "monthly"
    gaps = dates.diff().dropna()
    median_days = gaps.dt.days.median()
    if median_days <= 1.5:
        return "daily"
    if median_days <= 10:
        return "weekly"
    return "monthly"
