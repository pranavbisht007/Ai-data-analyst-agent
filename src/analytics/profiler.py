"""
src/analytics/profiler.py
High-level orchestrator: receives a cleaned DataFrame + config and
produces a structured AnalysisReport consumed by the detection engine
and the AI analyst.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from src.analytics.metrics import (
    aggregate_by_period,
    absolute_change,
    percentage_change,
    rolling_mean,
    rolling_median,
    series_mean,
    series_min,
    series_max,
    series_sum,
    series_count,
    linear_trend_slope,
    detect_interval,
)

logger = logging.getLogger(__name__)


@dataclass
class MetricSummary:
    metric_name: str
    period: str                        # 'daily' | 'weekly' | 'monthly'
    total: float
    mean: float
    median: float
    minimum: float
    maximum: float
    count: int
    latest_value: float
    previous_value: float
    abs_change: float
    pct_change: Optional[float]        # None if undefined
    trend_slope: Optional[float]       # None if too few periods
    aggregated: pd.DataFrame = field(default_factory=pd.DataFrame)  # [period, metric]


@dataclass
class AnalysisReport:
    dataset_id: int
    run_id: int
    date_col: str
    kpi_summaries: list[MetricSummary] = field(default_factory=list)
    data_quality_notes: list[str] = field(default_factory=list)


def build_report(
    df: pd.DataFrame,
    date_col: str,
    kpi_cols: list[str],
    dataset_id: int,
    run_id: int,
    period: Optional[str] = None,        # None = auto-detect
    agg_fn: str = "sum",
) -> AnalysisReport:
    report = AnalysisReport(dataset_id=dataset_id, run_id=run_id, date_col=date_col)

    # Auto-detect interval if not specified
    resolved_period = period or detect_interval(df, date_col)
    logger.info("Using period: %s for dataset %d", resolved_period, dataset_id)

    for col in kpi_cols:
        if col not in df.columns:
            report.data_quality_notes.append(f"Column '{col}' not found — skipped.")
            continue

        try:
            agg_df = aggregate_by_period(df, date_col, col, resolved_period, agg_fn)
        except Exception as exc:
            report.data_quality_notes.append(f"Aggregation failed for '{col}': {exc}")
            continue

        values = agg_df[col].dropna()
        if values.empty:
            report.data_quality_notes.append(f"'{col}' has no numeric data after aggregation.")
            continue

        latest = float(values.iloc[-1]) if len(values) >= 1 else float("nan")
        previous = float(values.iloc[-2]) if len(values) >= 2 else float("nan")
        abs_ch = absolute_change(latest, previous)
        pct_ch = percentage_change(latest, previous)
        slope = linear_trend_slope(values)

        summary = MetricSummary(
            metric_name=col,
            period=resolved_period,
            total=float(series_sum(values)),
            mean=float(series_mean(values)),
            median=float(pd.Series(values).median()),
            minimum=float(series_min(values)),
            maximum=float(series_max(values)),
            count=series_count(values),
            latest_value=latest,
            previous_value=previous,
            abs_change=abs_ch,
            pct_change=pct_ch,
            trend_slope=slope,
            aggregated=agg_df,
        )
        report.kpi_summaries.append(summary)

    return report
