"""tests/test_detector.py — Anomaly detection against known injected anomalies."""
from __future__ import annotations

import pandas as pd
import pytest

from src.analytics.metrics import aggregate_by_period
from src.detection.detector import detect_anomalies
from src.database.models import Severity


def _get_agg(sample_df, col, period="monthly"):
    return aggregate_by_period(sample_df, "date", col, period, "sum")


def test_revenue_drop_detected(sample_df):
    """Month 10 (index 9): revenue dropped from 115k to 60k — should be flagged."""
    agg = _get_agg(sample_df, "revenue")
    result = detect_anomalies(agg, "revenue", threshold_pct=20.0)
    assert any(
        a.period is not None and a.change_pct is not None and a.change_pct < -20
        for a in result.anomalies
    ), "Revenue drop should be detected"


def test_revenue_spike_detected(sample_df):
    """Month 16: revenue spiked to 200k — should be flagged."""
    agg = _get_agg(sample_df, "revenue")
    result = detect_anomalies(agg, "revenue", threshold_pct=20.0)
    assert any(
        a.change_pct is not None and a.change_pct > 20
        for a in result.anomalies
    ), "Revenue spike should be detected"


def test_visitor_spike_detected(sample_df):
    """Month 12: visitors jumped to 30k — should be flagged."""
    agg = _get_agg(sample_df, "website_visitors")
    result = detect_anomalies(agg, "website_visitors", threshold_pct=20.0)
    high_or_critical = [
        a for a in result.anomalies
        if a.severity in (Severity.high, Severity.critical)
    ]
    assert len(high_or_critical) > 0, "Visitor spike should be High or Critical"


def test_stable_expenses_no_anomaly(sample_df):
    """Expenses are consistently increasing — should produce no critical anomalies."""
    agg = _get_agg(sample_df, "expenses")
    result = detect_anomalies(agg, "expenses", threshold_pct=20.0)
    critical = [a for a in result.anomalies if a.severity == Severity.critical]
    assert len(critical) == 0, "Stable expenses should not produce critical anomalies"


def test_insufficient_history():
    """Fewer than MIN_HISTORY_PERIODS should skip baseline detection."""
    df = pd.DataFrame({"period": ["2024-01", "2024-02"], "revenue": [100, 200]})
    result = detect_anomalies(df, "revenue", threshold_pct=20.0)
    assert result.skipped_reason is not None


def test_anomaly_explanation_is_present(sample_df):
    """Every detected anomaly must have a non-empty explanation."""
    agg = _get_agg(sample_df, "revenue")
    result = detect_anomalies(agg, "revenue", threshold_pct=20.0)
    for a in result.anomalies:
        assert a.explanation, "All anomalies must have an explanation"


def test_anomaly_has_detection_method(sample_df):
    agg = _get_agg(sample_df, "revenue")
    result = detect_anomalies(agg, "revenue", threshold_pct=20.0)
    for a in result.anomalies:
        assert a.detection_method, "All anomalies must record detection_method"


def test_threshold_higher_reduces_anomalies(sample_df):
    """A 50% threshold should flag fewer anomalies than 20%."""
    agg = _get_agg(sample_df, "revenue")
    r20 = detect_anomalies(agg, "revenue", threshold_pct=20.0)
    r50 = detect_anomalies(agg, "revenue", threshold_pct=50.0)
    pct_anomalies_20 = [
        a for a in r20.anomalies if a.detection_method == "percentage_change_threshold"
    ]
    pct_anomalies_50 = [
        a for a in r50.anomalies if a.detection_method == "percentage_change_threshold"
    ]
    assert len(pct_anomalies_50) <= len(pct_anomalies_20)
