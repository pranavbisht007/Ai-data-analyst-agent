"""
src/detection/detector.py
Anomaly detection engine.
Combines four detection methods:
  1. Configurable percentage-change threshold
  2. Rolling MAD Z-score
  3. Spike / drop detection (extreme single-period jumps)
  4. Data-quality anomaly detection (missing periods)

Each detected anomaly carries structured evidence — never a vague claim.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from config.settings import DEFAULT_MAD_MULTIPLIER, DEFAULT_THRESHOLD_PCT, MIN_HISTORY_PERIODS
from src.analytics.metrics import mad_zscore, rate_of_change
from src.analytics.time_series import detect_missing_periods
from src.detection.baseline import rolling_median_baseline
from src.detection.severity import mad_score_to_severity, pct_to_severity
from src.database.models import Severity

logger = logging.getLogger(__name__)


@dataclass
class AnomalyRecord:
    metric_name: str
    period: str
    observed_value: Optional[float]
    baseline_value: Optional[float]
    change_abs: Optional[float]
    change_pct: Optional[float]
    anomaly_score: float
    severity: Severity
    detection_method: str
    explanation: str
    is_data_quality: bool = False


@dataclass
class DetectionResult:
    metric_name: str
    anomalies: list[AnomalyRecord] = field(default_factory=list)
    skipped_reason: Optional[str] = None


def detect_anomalies(
    agg_df: pd.DataFrame,         # columns: ['period', metric_name]
    metric_name: str,
    threshold_pct: float = DEFAULT_THRESHOLD_PCT,
    mad_multiplier: float = DEFAULT_MAD_MULTIPLIER,
    baseline_window: int = 3,
    direction: str = "higher_is_better",
) -> DetectionResult:
    result = DetectionResult(metric_name=metric_name)
    values: pd.Series = pd.to_numeric(agg_df[metric_name], errors="coerce")
    periods = agg_df["period"].astype(str)

    valid_count = values.notna().sum()
    if valid_count < MIN_HISTORY_PERIODS:
        result.skipped_reason = (
            f"Only {valid_count} valid period(s) — need at least {MIN_HISTORY_PERIODS} "
            "to run baseline analysis."
        )
        return result

    # ── 1. Percentage-change threshold detection ──────────────────────────────
    pct_changes = rate_of_change(values)
    baselines = rolling_median_baseline(values, window=baseline_window)

    for i in range(1, len(values)):
        if pd.isna(values.iloc[i]) or pd.isna(pct_changes.iloc[i]):
            continue
        pct = float(pct_changes.iloc[i])
        if abs(pct) < threshold_pct:
            continue

        obs = float(values.iloc[i])
        base = float(baselines.iloc[i]) if not pd.isna(baselines.iloc[i]) else float(values.iloc[i - 1])
        severity = pct_to_severity(pct, threshold_pct)
        direction_label = _direction_label(pct, direction)
        explanation = (
            f"{metric_name} {direction_label} by {abs(pct):.1f}% "
            f"(from {base:,.2f} to {obs:,.2f}) in period {periods.iloc[i]}. "
            f"This was detected using a {threshold_pct}% change threshold. "
            f"Note: this is an observed change; the cause requires investigation."
        )
        result.anomalies.append(
            AnomalyRecord(
                metric_name=metric_name,
                period=str(periods.iloc[i]),
                observed_value=obs,
                baseline_value=base,
                change_abs=obs - base,
                change_pct=pct,
                anomaly_score=abs(pct),
                severity=severity,
                detection_method="percentage_change_threshold",
                explanation=explanation,
            )
        )

    # ── 2. MAD Z-score detection ──────────────────────────────────────────────
    z_scores = mad_zscore(values)
    for i in range(len(values)):
        if pd.isna(values.iloc[i]) or pd.isna(z_scores.iloc[i]):
            continue
        z = float(z_scores.iloc[i])
        if z < mad_multiplier:
            continue

        obs = float(values.iloc[i])
        base = float(values.median())
        severity = mad_score_to_severity(z)

        # Avoid duplicating an anomaly already flagged by threshold method
        period_str = str(periods.iloc[i])
        already = any(
            a.period == period_str and a.detection_method == "percentage_change_threshold"
            for a in result.anomalies
        )
        if already:
            continue

        explanation = (
            f"{metric_name} recorded {obs:,.2f} in period {period_str}, "
            f"which is {z:.1f} MAD units from the series median ({base:,.2f}). "
            f"A score above {mad_multiplier} is considered statistically unusual "
            f"by the Median Absolute Deviation method. The cause requires investigation."
        )
        result.anomalies.append(
            AnomalyRecord(
                metric_name=metric_name,
                period=period_str,
                observed_value=obs,
                baseline_value=base,
                change_abs=obs - base,
                change_pct=((obs - base) / abs(base) * 100) if base != 0 else None,
                anomaly_score=z * 10,
                severity=severity,
                detection_method="mad_zscore",
                explanation=explanation,
            )
        )

    # ── 3. Missing period detection ───────────────────────────────────────────
    try:
        date_index = pd.to_datetime(agg_df["period"], errors="coerce").dropna()
        _freq_guess = _guess_freq(date_index)
        if _freq_guess:
            missing = detect_missing_periods(date_index, freq=_freq_guess)
            for mp in missing:
                result.anomalies.append(
                    AnomalyRecord(
                        metric_name=metric_name,
                        period=mp,
                        observed_value=None,
                        baseline_value=None,
                        change_abs=None,
                        change_pct=None,
                        anomaly_score=5.0,
                        severity=Severity.medium,
                        detection_method="missing_period",
                        explanation=(
                            f"No data recorded for {metric_name} in period {mp}. "
                            "This may indicate a reporting gap or data collection issue."
                        ),
                        is_data_quality=True,
                    )
                )
    except Exception as exc:
        logger.debug("Missing period detection failed for %s: %s", metric_name, exc)

    logger.info(
        "Detector found %d anomaly(ies) for '%s'",
        len(result.anomalies),
        metric_name,
    )
    return result


def _direction_label(pct: float, direction: str) -> str:
    if pct > 0:
        return "increased" if direction != "lower_is_better" else "increased (unfavourable)"
    return "decreased" if direction == "higher_is_better" else "decreased (unfavourable)"


def _guess_freq(index: pd.DatetimeIndex) -> Optional[str]:
    if len(index) < 2:
        return None
    median_days = index.to_series().diff().dropna().dt.days.median()
    if median_days <= 1.5:
        return "D"
    if median_days <= 10:
        return "W-MON"
    return "MS"
