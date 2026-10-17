"""
src/alerts/rules.py
Alert rule evaluation: checks severity threshold and deduplication.
"""
from __future__ import annotations

import logging
from typing import Optional

from src.alerts.deduplication import make_dedup_key
from src.alerts.email_service import send_alert
from src.database.db import get_session
from src.database.models import Severity
from src.database.repository import alert_dedup_key_exists, save_alert
from src.detection.detector import AnomalyRecord

logger = logging.getLogger(__name__)

_SEVERITY_ORDER = {
    Severity.low: 0,
    Severity.medium: 1,
    Severity.high: 2,
    Severity.critical: 3,
}


def process_alerts(
    anomalies: list[AnomalyRecord],
    anomaly_db_ids: dict[str, int],   # maps period|metric to DB anomaly id
    recipients: list[str],
    min_severity: Severity,
    business_name: str,
    alerts_enabled: bool,
) -> list[dict]:
    """
    Evaluate rules and send emails for qualifying anomalies.
    Returns a list of alert result dicts for logging.
    """
    results = []
    if not alerts_enabled:
        logger.info("Email alerts are disabled — skipping.")
        return results
    if not recipients:
        logger.info("No alert recipients configured — skipping.")
        return results

    min_order = _SEVERITY_ORDER.get(min_severity, 0)

    for anomaly in anomalies:
        order = _SEVERITY_ORDER.get(anomaly.severity, 0)
        if order < min_order:
            continue  # below configured threshold

        dedup_key = make_dedup_key(
            anomaly.metric_name, anomaly.period, anomaly.severity.value
        )
        db_anomaly_id = anomaly_db_ids.get(f"{anomaly.metric_name}|{anomaly.period}")

        with get_session() as session:
            if alert_dedup_key_exists(session, dedup_key):
                logger.info(
                    "Alert deduplication: skipping %s / %s (already sent).",
                    anomaly.metric_name,
                    anomaly.period,
                )
                if db_anomaly_id:
                    save_alert(
                        session,
                        anomaly_id=db_anomaly_id,
                        recipient=", ".join(recipients),
                        dedup_key=dedup_key,
                        status="skipped",
                    )
                results.append({"anomaly": anomaly, "status": "skipped"})
                continue

            ok, error = send_alert(anomaly, recipients, business_name)
            status = "sent" if ok else "failed"

            if db_anomaly_id:
                save_alert(
                    session,
                    anomaly_id=db_anomaly_id,
                    recipient=", ".join(recipients),
                    dedup_key=dedup_key,
                    status=status,
                    last_error=error,
                )

            results.append({"anomaly": anomaly, "status": status, "error": error})

    return results
