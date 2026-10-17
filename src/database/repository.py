"""
src/database/repository.py
Data-access layer.  All DB interactions go through this module so that
the rest of the application never builds raw SQL strings.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.database.models import (
    AnalysisRun,
    AlertHistory,
    Anomaly,
    AnomalyStatus,
    BusinessProfile,
    Dataset,
    DatasetStatus,
    MetricConfig,
    RunStatus,
    RunTrigger,
    Severity,
)

logger = logging.getLogger(__name__)


# ── Business Profile ──────────────────────────────────────────────────────────

def upsert_profile(
    session: Session,
    name: str,
    industry: str = "",
    description: str = "",
    timezone_str: str = "UTC",
    notes: str = "",
) -> BusinessProfile:
    profile = session.query(BusinessProfile).filter_by(name=name).first()
    if profile is None:
        profile = BusinessProfile(
            name=name,
            industry=industry,
            description=description,
            timezone=timezone_str,
            notes=notes,
        )
        session.add(profile)
    else:
        profile.industry = industry
        profile.description = description
        profile.timezone = timezone_str
        profile.notes = notes
        profile.updated_at = datetime.now(timezone.utc)
    session.flush()
    return profile


def get_profile(session: Session, profile_id: int) -> Optional[BusinessProfile]:
    return session.get(BusinessProfile, profile_id)


def list_profiles(session: Session) -> list[BusinessProfile]:
    return session.query(BusinessProfile).order_by(BusinessProfile.created_at.desc()).all()


# ── Dataset ───────────────────────────────────────────────────────────────────

def create_dataset(
    session: Session,
    file_name: str,
    file_path: str,
    file_hash: str,
    sheet_name: str = "",
    profile_id: Optional[int] = None,
    row_count: Optional[int] = None,
    col_count: Optional[int] = None,
    date_column: Optional[str] = None,
) -> Dataset:
    ds = Dataset(
        file_name=file_name,
        file_path=file_path,
        file_hash=file_hash,
        sheet_name=sheet_name,
        profile_id=profile_id,
        row_count=row_count,
        col_count=col_count,
        date_column=date_column,
        status=DatasetStatus.pending,
    )
    session.add(ds)
    session.flush()
    return ds


def update_dataset_status(
    session: Session,
    dataset_id: int,
    status: DatasetStatus,
    validation_notes: str = "",
) -> None:
    ds = session.get(Dataset, dataset_id)
    if ds:
        ds.status = status
        ds.validation_notes = validation_notes


def get_dataset(session: Session, dataset_id: int) -> Optional[Dataset]:
    return session.get(Dataset, dataset_id)


def list_datasets(
    session: Session, profile_id: Optional[int] = None, limit: int = 50
) -> list[Dataset]:
    q = session.query(Dataset).order_by(Dataset.uploaded_at.desc())
    if profile_id is not None:
        q = q.filter(Dataset.profile_id == profile_id)
    return q.limit(limit).all()


def dataset_hash_exists(session: Session, file_hash: str) -> bool:
    return (
        session.query(Dataset).filter_by(file_hash=file_hash).first() is not None
    )


# ── Metric Config ─────────────────────────────────────────────────────────────

def upsert_metric_config(
    session: Session,
    profile_id: int,
    metric_name: str,
    **kwargs,
) -> MetricConfig:
    mc = (
        session.query(MetricConfig)
        .filter_by(profile_id=profile_id, metric_name=metric_name)
        .first()
    )
    if mc is None:
        mc = MetricConfig(profile_id=profile_id, metric_name=metric_name, **kwargs)
        session.add(mc)
    else:
        for k, v in kwargs.items():
            setattr(mc, k, v)
    session.flush()
    return mc


def list_metric_configs(
    session: Session, profile_id: int
) -> list[MetricConfig]:
    return (
        session.query(MetricConfig)
        .filter_by(profile_id=profile_id, enabled=True)
        .all()
    )


# ── Analysis Run ──────────────────────────────────────────────────────────────

def start_run(
    session: Session,
    dataset_id: int,
    trigger: RunTrigger = RunTrigger.manual,
) -> AnalysisRun:
    run = AnalysisRun(
        dataset_id=dataset_id,
        trigger_type=trigger,
        status=RunStatus.running,
    )
    session.add(run)
    session.flush()
    return run


def finish_run(
    session: Session,
    run_id: int,
    status: RunStatus,
    summary: str = "",
) -> None:
    run = session.get(AnalysisRun, run_id)
    if run:
        run.finished_at = datetime.now(timezone.utc)
        run.status = status
        run.summary = summary


def list_runs(
    session: Session,
    dataset_id: Optional[int] = None,
    limit: int = 20,
) -> list[AnalysisRun]:
    q = session.query(AnalysisRun).order_by(AnalysisRun.started_at.desc())
    if dataset_id is not None:
        q = q.filter(AnalysisRun.dataset_id == dataset_id)
    return q.limit(limit).all()


# ── Anomaly ───────────────────────────────────────────────────────────────────

def save_anomaly(session: Session, run_id: int, **fields) -> Anomaly:
    a = Anomaly(run_id=run_id, **fields)
    session.add(a)
    session.flush()
    return a


def list_anomalies(
    session: Session,
    run_id: Optional[int] = None,
    severity: Optional[Severity] = None,
    status: Optional[AnomalyStatus] = None,
    limit: int = 200,
) -> list[Anomaly]:
    q = session.query(Anomaly).order_by(Anomaly.created_at.desc())
    if run_id is not None:
        q = q.filter(Anomaly.run_id == run_id)
    if severity is not None:
        q = q.filter(Anomaly.severity == severity)
    if status is not None:
        q = q.filter(Anomaly.status == status)
    return q.limit(limit).all()


def update_anomaly_status(
    session: Session, anomaly_id: int, status: AnomalyStatus
) -> None:
    a = session.get(Anomaly, anomaly_id)
    if a:
        a.status = status


# ── Alert History ─────────────────────────────────────────────────────────────

def save_alert(
    session: Session,
    anomaly_id: int,
    recipient: str,
    dedup_key: str,
    status: str,
    attempt_count: int = 1,
    last_error: str = "",
) -> AlertHistory:
    from src.database.models import AlertStatus

    ah = AlertHistory(
        anomaly_id=anomaly_id,
        recipient=recipient,
        dedup_key=dedup_key,
        status=AlertStatus(status),
        attempt_count=attempt_count,
        sent_at=datetime.now(timezone.utc) if status == "sent" else None,
        last_error=last_error or None,
    )
    session.add(ah)
    session.flush()
    return ah


def alert_dedup_key_exists(session: Session, dedup_key: str) -> bool:
    from src.database.models import AlertStatus

    return (
        session.query(AlertHistory)
        .filter(
            AlertHistory.dedup_key == dedup_key,
            AlertHistory.status == AlertStatus.sent,
        )
        .first()
        is not None
    )
