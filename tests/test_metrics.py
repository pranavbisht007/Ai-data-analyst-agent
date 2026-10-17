"""tests/test_metrics.py — Verify KPI calculations against known values."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.analytics.metrics import (
    absolute_change,
    aggregate_by_period,
    detect_interval,
    linear_trend_slope,
    mad_zscore,
    percentage_change,
    rate_of_change,
    rolling_mean,
    rolling_median,
    series_mean,
    series_min,
    series_max,
    series_sum,
    series_count,
)


def test_series_sum():
    s = pd.Series([10, 20, 30])
    assert series_sum(s) == 60.0


def test_series_mean():
    s = pd.Series([10.0, 20.0, 30.0])
    assert series_mean(s) == 20.0


def test_series_min():
    s = pd.Series([5, 3, 8, 1])
    assert series_min(s) == 1.0


def test_series_max():
    s = pd.Series([5, 3, 8, 1])
    assert series_max(s) == 8.0


def test_series_count_ignores_nan():
    s = pd.Series([1, None, 3, None])
    assert series_count(s) == 2


def test_absolute_change():
    assert absolute_change(120.0, 100.0) == pytest.approx(20.0)


def test_absolute_change_negative():
    assert absolute_change(80.0, 100.0) == pytest.approx(-20.0)


def test_percentage_change():
    result = percentage_change(120.0, 100.0)
    assert result == pytest.approx(20.0)


def test_percentage_change_zero_previous_returns_none():
    assert percentage_change(50.0, 0.0) is None


def test_percentage_change_nan():
    assert percentage_change(float("nan"), 100.0) is None


def test_rolling_mean_window_3():
    s = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
    result = rolling_mean(s, 3)
    assert result.iloc[-1] == pytest.approx(40.0)


def test_rolling_median():
    s = pd.Series([1.0, 100.0, 2.0, 3.0, 4.0])
    result = rolling_median(s, 3)
    assert len(result) == 5


def test_linear_trend_slope_increasing():
    s = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
    slope = linear_trend_slope(s)
    assert slope is not None
    assert slope > 0


def test_linear_trend_slope_insufficient_data():
    s = pd.Series([10.0, 20.0])
    assert linear_trend_slope(s) is None


def test_mad_zscore_outlier():
    # 1000 is far from the median of ~5
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 1000.0])
    z = mad_zscore(s)
    assert z.iloc[-1] > 10  # clearly anomalous


def test_mad_zscore_constant_series():
    s = pd.Series([5.0, 5.0, 5.0, 5.0])
    z = mad_zscore(s)
    assert all(z == 0.0)


def test_aggregate_by_period_monthly(sample_df):
    result = aggregate_by_period(sample_df, "date", "revenue", "monthly", "sum")
    assert "period" in result.columns
    assert "revenue" in result.columns
    assert len(result) == 18  # 18 months


def test_detect_interval_monthly(sample_df):
    interval = detect_interval(sample_df, "date")
    assert interval == "monthly"


def test_detect_interval_daily():
    df = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=10, freq="D"),
        "value": range(10),
    })
    assert detect_interval(df, "date") == "daily"


def test_rate_of_change_known():
    s = pd.Series([100.0, 150.0, 75.0])
    roc = rate_of_change(s)
    assert roc.iloc[1] == pytest.approx(50.0)   # +50%
    assert roc.iloc[2] == pytest.approx(-50.0)  # -50%
