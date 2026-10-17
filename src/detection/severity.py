"""
src/detection/severity.py
Maps anomaly scores / percentage changes to severity labels.
"""
from __future__ import annotations

from src.database.models import Severity


def score_to_severity(score: float, threshold_pct: float = 20.0) -> Severity:
    """
    score is the absolute percentage change (or MAD z-score * 10 for consistency).
    Thresholds are relative to the configured threshold_pct.
    """
    if score >= threshold_pct * 4:
        return Severity.critical
    if score >= threshold_pct * 2:
        return Severity.high
    if score >= threshold_pct:
        return Severity.medium
    return Severity.low


def pct_to_severity(pct_change: float, threshold_pct: float = 20.0) -> Severity:
    abs_pct = abs(pct_change)
    return score_to_severity(abs_pct, threshold_pct)


def mad_score_to_severity(mad_z: float) -> Severity:
    """MAD Z-score thresholds: >8 critical, >6 high, >3 medium, else low."""
    if mad_z >= 8:
        return Severity.critical
    if mad_z >= 6:
        return Severity.high
    if mad_z >= 3:
        return Severity.medium
    return Severity.low
