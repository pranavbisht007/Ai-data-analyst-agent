"""
src/agent/business_context.py
Helpers for structuring business context data before sending to the AI.
"""
from __future__ import annotations

from src.analytics.profiler import AnalysisReport, MetricSummary
from src.detection.detector import AnomalyRecord


def format_kpi_summaries(report: AnalysisReport) -> str:
    lines = []
    for s in report.kpi_summaries:
        pct_str = f"{s.pct_change:+.1f}%" if s.pct_change is not None else "N/A (undefined)"
        lines.append(
            f"- {s.metric_name} ({s.period}): "
            f"latest={s.latest_value:,.2f}, prev={s.previous_value:,.2f}, "
            f"change={s.abs_change:+,.2f} ({pct_str}), "
            f"mean={s.mean:,.2f}, total={s.total:,.2f}"
        )
    return "\n".join(lines) if lines else "No KPI summaries available."


def format_anomalies(anomalies: list[AnomalyRecord]) -> str:
    if not anomalies:
        return "No anomalies detected."
    lines = []
    for a in anomalies:
        obs = f"{a.observed_value:,.2f}" if a.observed_value is not None else "N/A"
        base = f"{a.baseline_value:,.2f}" if a.baseline_value is not None else "N/A"
        pct = f"{a.change_pct:+.1f}%" if a.change_pct is not None else "N/A"
        lines.append(
            f"[{a.severity.value}] {a.metric_name} | {a.period} | "
            f"observed={obs} | baseline={base} | change={pct} | "
            f"method={a.detection_method}"
        )
    return "\n".join(lines)


def format_quality_notes(notes: list[str]) -> str:
    if not notes:
        return "No data quality issues."
    return "\n".join(f"- {n}" for n in notes)
