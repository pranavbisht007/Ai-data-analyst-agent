"""tests/test_alerts.py — Alert deduplication and rule evaluation."""
from __future__ import annotations

import pytest

from src.alerts.deduplication import make_dedup_key
from src.database.models import Severity


def test_dedup_key_is_deterministic():
    k1 = make_dedup_key("revenue", "2024-10", "Critical")
    k2 = make_dedup_key("revenue", "2024-10", "Critical")
    assert k1 == k2


def test_dedup_key_differs_by_metric():
    k1 = make_dedup_key("revenue", "2024-10", "High")
    k2 = make_dedup_key("orders", "2024-10", "High")
    assert k1 != k2


def test_dedup_key_differs_by_period():
    k1 = make_dedup_key("revenue", "2024-10", "High")
    k2 = make_dedup_key("revenue", "2024-11", "High")
    assert k1 != k2


def test_dedup_key_differs_by_severity():
    k1 = make_dedup_key("revenue", "2024-10", "High")
    k2 = make_dedup_key("revenue", "2024-10", "Low")
    assert k1 != k2


def test_dedup_key_length():
    k = make_dedup_key("revenue", "2024-10", "Critical")
    assert len(k) == 64


def test_no_email_without_config(monkeypatch):
    """send_alert must return False when SMTP is not configured."""
    monkeypatch.setattr("src.alerts.email_service.SMTP_HOST", "")
    monkeypatch.setattr("src.alerts.email_service.SMTP_USER", "")
    monkeypatch.setattr("src.alerts.email_service.SMTP_PASSWORD", "")

    from src.alerts.email_service import send_alert
    from src.detection.detector import AnomalyRecord

    a = AnomalyRecord(
        metric_name="revenue", period="2024-10",
        observed_value=60_000, baseline_value=115_000,
        change_abs=-55_000, change_pct=-47.8,
        anomaly_score=47.8, severity=Severity.critical,
        detection_method="pct", explanation="test",
    )
    ok, err = send_alert(a, ["test@example.com"], "Test Co")
    assert not ok
    assert "Email is not configured" in err or "Missing" in err


def test_no_email_without_recipients(monkeypatch):
    from src.alerts.email_service import send_alert
    from src.detection.detector import AnomalyRecord

    a = AnomalyRecord(
        metric_name="revenue", period="2024-10",
        observed_value=60_000, baseline_value=115_000,
        change_abs=-55_000, change_pct=-47.8,
        anomaly_score=47.8, severity=Severity.critical,
        detection_method="pct", explanation="test",
    )
    ok, err = send_alert(a, [], "Test Co")
    assert not ok
    assert "recipients" in err.lower()
