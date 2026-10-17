"""
src/alerts/deduplication.py
Alert deduplication — prevents sending repeated emails for the same ongoing anomaly.
"""
from __future__ import annotations

import hashlib


def make_dedup_key(metric_name: str, period: str, severity: str) -> str:
    """Stable hash key for an anomaly instance."""
    raw = f"{metric_name}|{period}|{severity}"
    return hashlib.sha256(raw.encode()).hexdigest()[:64]
