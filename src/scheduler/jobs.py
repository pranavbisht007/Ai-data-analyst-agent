"""
src/scheduler/jobs.py
APScheduler job definitions.  The scheduler runs as a separate process
(run_scheduler.py) and is NOT embedded in Streamlit.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from src.analytics.profiler import build_report
from src.database.db import get_session
from src.database.models import RunTrigger, RunStatus
from src.database.repository import (
    finish_run,
    get_dataset,
    list_datasets,
    list_metric_configs,
    save_anomaly,
    start_run,
)
from src.detection.detector import detect_anomalies
from src.ingestion.excel_reader import read_sheet

logger = logging.getLogger(__name__)


def run_analysis_job(
    dataset_id: int,
    kpi_cols: list[str],
    date_col: str,
    trigger: RunTrigger = RunTrigger.scheduled,
    profile_id: Optional[int] = None,
    period: Optional[str] = None,
    threshold_pct: float = 20.0,
) -> Optional[int]:
    """
    Full analysis pipeline for a single dataset.
    Returns the run_id on success, None on failure.
    """
    with get_session() as session:
        ds = get_dataset(session, dataset_id)
        if ds is None:
            logger.error("Dataset %d not found.", dataset_id)
            return None

        file_path = Path(ds.file_path)
        sheet = ds.sheet_name or "Sheet1"

        run = start_run(session, dataset_id=dataset_id, trigger=trigger)
        run_id = run.id

    try:
        df = read_sheet(file_path, sheet)
        report = build_report(
            df=df,
            date_col=date_col,
            kpi_cols=kpi_cols,
            dataset_id=dataset_id,
            run_id=run_id,
            period=period,
        )

        all_anomalies = []
        with get_session() as session:
            for summary in report.kpi_summaries:
                detection = detect_anomalies(
                    summary.aggregated,
                    summary.metric_name,
                    threshold_pct=threshold_pct,
                )
                for a in detection.anomalies:
                    save_anomaly(
                        session,
                        run_id=run_id,
                        metric_name=a.metric_name,
                        period=a.period,
                        observed_value=a.observed_value,
                        baseline_value=a.baseline_value,
                        change_abs=a.change_abs,
                        change_pct=a.change_pct,
                        anomaly_score=a.anomaly_score,
                        severity=a.severity,
                        detection_method=a.detection_method,
                        explanation=a.explanation,
                    )
                    all_anomalies.append(a)

            n_anomalies = len(all_anomalies)
            n_kpis = len(report.kpi_summaries)
            summary_text = (
                f"Analysed {n_kpis} KPI(s). Detected {n_anomalies} anomaly(ies)."
            )
            finish_run(session, run_id, RunStatus.completed, summary_text)

        logger.info("Job completed: run_id=%d, %s", run_id, summary_text)
        return run_id

    except Exception as exc:
        logger.exception("Job failed for dataset %d: %s", dataset_id, exc)
        with get_session() as session:
            finish_run(session, run_id, RunStatus.failed, str(exc))
        return None
