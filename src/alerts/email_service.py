"""
src/alerts/email_service.py
SMTP email alert service.
- Credentials come exclusively from environment variables.
- Passwords are NEVER logged, stored in the DB, or printed.
- Retry logic with exponential back-off for transient failures.
- Never sends email unless recipients are explicitly configured.
"""
from __future__ import annotations

import logging
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from config.settings import (
    ALERT_FROM_NAME,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USE_TLS,
    SMTP_USER,
)
from src.detection.detector import AnomalyRecord

logger = logging.getLogger(__name__)


class EmailConfigError(Exception):
    """Raised when SMTP configuration is incomplete."""


def _check_config() -> None:
    missing = [k for k, v in {
        "SMTP_HOST": SMTP_HOST,
        "SMTP_USER": SMTP_USER,
        "SMTP_PASSWORD": SMTP_PASSWORD,
    }.items() if not v]
    if missing:
        raise EmailConfigError(
            f"Email is not configured. Missing environment variables: {', '.join(missing)}."
        )


def _build_email_body(anomaly: AnomalyRecord, business_name: str) -> str:
    obs = f"{anomaly.observed_value:,.2f}" if anomaly.observed_value is not None else "N/A"
    base = f"{anomaly.baseline_value:,.2f}" if anomaly.baseline_value is not None else "N/A"
    pct = f"{anomaly.change_pct:+.1f}%" if anomaly.change_pct is not None else "N/A"
    return f"""Business Alert — {business_name}
{'=' * 50}

Severity  : {anomaly.severity.value}
Metric    : {anomaly.metric_name}
Period    : {anomaly.period}
Observed  : {obs}
Baseline  : {base}
Change    : {pct}
Method    : {anomaly.detection_method}

Explanation
-----------
{anomaly.explanation}

Recommended Action
------------------
Please review the data for this period and investigate whether external
factors, data entry errors, or genuine business changes explain this result.

---
This alert was generated automatically by the AI Data Analyst Agent.
To stop receiving alerts, update your Alert Settings in the application.
"""


def send_alert(
    anomaly: AnomalyRecord,
    recipients: list[str],
    business_name: str = "Your Business",
    max_retries: int = 3,
) -> tuple[bool, str]:
    """
    Send an anomaly alert email.
    Returns (success, error_message).
    Never raises — caller is responsible for retry/dedup logic.
    """
    if not recipients:
        return False, "No recipients configured."

    try:
        _check_config()
    except EmailConfigError as exc:
        return False, str(exc)

    subject = f"[{anomaly.severity.value}] {anomaly.metric_name} anomaly — {anomaly.period}"
    body = _build_email_body(anomaly, business_name)

    for attempt in range(1, max_retries + 1):
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{ALERT_FROM_NAME} <{SMTP_USER}>"
            msg["To"] = ", ".join(recipients)
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
                if SMTP_USE_TLS:
                    server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)  # password not logged
                server.sendmail(SMTP_USER, recipients, msg.as_string())

            logger.info(
                "Alert email sent for %s / %s to %d recipient(s).",
                anomaly.metric_name,
                anomaly.period,
                len(recipients),
            )
            return True, ""

        except smtplib.SMTPAuthenticationError:
            return False, "SMTP authentication failed. Check SMTP_USER and SMTP_PASSWORD."

        except (smtplib.SMTPException, OSError) as exc:
            logger.warning("Email attempt %d/%d failed: %s", attempt, max_retries, exc)
            if attempt < max_retries:
                time.sleep(2 ** attempt)  # exponential back-off

    return False, f"Email failed after {max_retries} attempts."


def send_test_email(recipient: str) -> tuple[bool, str]:
    """Send a plain test email to verify SMTP configuration."""
    try:
        _check_config()
    except EmailConfigError as exc:
        return False, str(exc)

    subject = "Data Analyst Agent — SMTP Test"
    body = (
        "This is a test email from the AI Data Analyst Agent.\n"
        "If you received this, your SMTP configuration is working correctly.\n"
    )
    try:
        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"] = f"{ALERT_FROM_NAME} <{SMTP_USER}>"
        msg["To"] = recipient
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            if SMTP_USE_TLS:
                server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, [recipient], msg.as_string())

        return True, ""
    except Exception as exc:
        return False, str(exc)
