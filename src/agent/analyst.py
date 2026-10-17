"""
src/agent/analyst.py
AI business analyst.  Uses the google-genai SDK.
Falls back to a statistical-only summary when no API key is configured.
API key is NEVER logged, stored, or displayed.
"""
from __future__ import annotations

import logging
from typing import Optional

from config.settings import GEMINI_API_KEY, GEMINI_MODEL
from src.agent.business_context import (
    format_anomalies,
    format_kpi_summaries,
    format_quality_notes,
)
from src.agent.prompts import SYSTEM_PROMPT, build_analysis_prompt
from src.analytics.profiler import AnalysisReport
from src.detection.detector import AnomalyRecord

logger = logging.getLogger(__name__)


def _statistical_fallback(report: AnalysisReport, anomalies: list[AnomalyRecord]) -> str:
    """Generate a plain-text summary without AI when no API key is configured."""
    lines = [
        "STATISTICAL SUMMARY",
        "=" * 40,
        "(AI-generated commentary is unavailable — no Gemini API key configured.)",
        "",
        "KPI OVERVIEW",
        "-" * 40,
    ]
    for s in report.kpi_summaries:
        pct_str = f"{s.pct_change:+.1f}%" if s.pct_change is not None else "undefined"
        direction = "up" if (s.pct_change or 0) > 0 else "down"
        lines.append(
            f"  {s.metric_name}: latest={s.latest_value:,.2f}, "
            f"prev={s.previous_value:,.2f}, change={pct_str} ({direction})"
        )

    if anomalies:
        lines += ["", "DETECTED ANOMALIES", "-" * 40]
        for a in anomalies:
            lines.append(f"  [{a.severity.value}] {a.metric_name} — {a.period}: {a.explanation}")
    else:
        lines += ["", "No anomalies detected."]

    if report.data_quality_notes:
        lines += ["", "DATA QUALITY NOTES", "-" * 40]
        for n in report.data_quality_notes:
            lines.append(f"  - {n}")

    return "\n".join(lines)


def run_ai_analysis(
    report: AnalysisReport,
    anomalies: list[AnomalyRecord],
    business_name: str = "",
    industry: str = "",
    description: str = "",
    notes: str = "",
) -> tuple[str, bool]:
    """
    Returns (analysis_text, ai_was_used).
    Falls back gracefully when API key is absent.
    """
    if not GEMINI_API_KEY:
        logger.info("No Gemini API key — using statistical fallback.")
        return _statistical_fallback(report, anomalies), False

    try:
        from google import genai  # type: ignore

        client = genai.Client(api_key=GEMINI_API_KEY)

        prompt = build_analysis_prompt(
            business_name=business_name,
            industry=industry,
            description=description,
            notes=notes,
            kpi_summaries=format_kpi_summaries(report),
            anomaly_list=format_anomalies(anomalies),
            quality_notes=format_quality_notes(report.data_quality_notes),
        )

        interaction = client.interactions.create(
            model=GEMINI_MODEL,
            system_instruction=SYSTEM_PROMPT,
            input=prompt,
            store=False,  # do not retain business data on Google servers
        )
        text = interaction.output_text or ""
        if not text.strip():
            raise ValueError("Empty response from AI model.")

        logger.info("AI analysis completed successfully.")
        return text, True

    except Exception as exc:
        # Log error without exposing the API key
        logger.error("AI analysis failed: %s", exc)
        fallback = _statistical_fallback(report, anomalies)
        return (
            f"AI analysis encountered an error and fell back to statistical summary.\n\n"
            f"{fallback}"
        ), False
