"""
src/database/models.py
SQLAlchemy ORM models with foreign keys, indexes, and constraints.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ── Enums ─────────────────────────────────────────────────────────────────────

class DatasetStatus(str, enum.Enum):
    pending = "pending"
    valid = "valid"
    invalid = "invalid"
    processed = "processed"


class RunStatus(str, enum.Enum):
    running = "running"
    completed = "completed"
    failed = "failed"


class RunTrigger(str, enum.Enum):
    upload = "upload"
    scheduled = "scheduled"
    manual = "manual"


class Severity(str, enum.Enum):
    low = "Low"
    medium = "Medium"
    high = "High"
    critical = "Critical"


class AnomalyStatus(str, enum.Enum):
    open = "open"
    acknowledged = "acknowledged"
    resolved = "resolved"


class AlertStatus(str, enum.Enum):
    sent = "sent"
    failed = "failed"
    skipped = "skipped"


class AggregationType(str, enum.Enum):
    sum = "sum"
    mean = "mean"
    max = "max"
    min = "min"


class Interval(str, enum.Enum):
    auto = "auto"
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"


class Direction(str, enum.Enum):
    higher_is_better = "higher_is_better"
    lower_is_better = "lower_is_better"
    neutral = "neutral"


# ── Tables ────────────────────────────────────────────────────────────────────

class BusinessProfile(Base):
    __tablename__ = "business_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(String(60), default="UTC")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    datasets: Mapped[list[Dataset]] = relationship("Dataset", back_populates="profile")
    metric_configs: Mapped[list[MetricConfig]] = relationship(
        "MetricConfig", back_populates="profile"
    )


class Dataset(Base):
    __tablename__ = "datasets"
    __table_args__ = (
        Index("ix_datasets_profile_id", "profile_id"),
        Index("ix_datasets_file_hash", "file_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("business_profiles.id", ondelete="SET NULL")
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    sheet_name: Mapped[str | None] = mapped_column(String(100))
    row_count: Mapped[int | None] = mapped_column(Integer)
    col_count: Mapped[int | None] = mapped_column(Integer)
    date_column: Mapped[str | None] = mapped_column(String(100))
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    status: Mapped[DatasetStatus] = mapped_column(
        Enum(DatasetStatus), default=DatasetStatus.pending, nullable=False
    )
    validation_notes: Mapped[str | None] = mapped_column(Text)

    profile: Mapped[BusinessProfile | None] = relationship(
        "BusinessProfile", back_populates="datasets"
    )
    analysis_runs: Mapped[list[AnalysisRun]] = relationship(
        "AnalysisRun", back_populates="dataset"
    )


class MetricConfig(Base):
    __tablename__ = "metric_configs"
    __table_args__ = (
        UniqueConstraint("profile_id", "metric_name", name="uq_metric_per_profile"),
        Index("ix_metric_configs_profile_id", "profile_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("business_profiles.id", ondelete="CASCADE"), nullable=False
    )
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    date_column: Mapped[str | None] = mapped_column(String(100))
    aggregation: Mapped[AggregationType] = mapped_column(
        Enum(AggregationType), default=AggregationType.sum
    )
    interval: Mapped[Interval] = mapped_column(Enum(Interval), default=Interval.auto)
    threshold_pct: Mapped[float] = mapped_column(Float, default=20.0)
    direction: Mapped[Direction] = mapped_column(
        Enum(Direction), default=Direction.higher_is_better
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    profile: Mapped[BusinessProfile] = relationship(
        "BusinessProfile", back_populates="metric_configs"
    )


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        Index("ix_analysis_runs_dataset_id", "dataset_id"),
        Index("ix_analysis_runs_started_at", "started_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trigger_type: Mapped[RunTrigger] = mapped_column(
        Enum(RunTrigger), default=RunTrigger.manual, nullable=False
    )
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus), default=RunStatus.running, nullable=False
    )
    summary: Mapped[str | None] = mapped_column(Text)

    dataset: Mapped[Dataset] = relationship("Dataset", back_populates="analysis_runs")
    anomalies: Mapped[list[Anomaly]] = relationship(
        "Anomaly", back_populates="run", cascade="all, delete-orphan"
    )


class Anomaly(Base):
    __tablename__ = "anomalies"
    __table_args__ = (
        Index("ix_anomalies_run_id", "run_id"),
        Index("ix_anomalies_severity", "severity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False
    )
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    period: Mapped[str] = mapped_column(String(50), nullable=False)
    observed_value: Mapped[float | None] = mapped_column(Float)
    baseline_value: Mapped[float | None] = mapped_column(Float)
    change_abs: Mapped[float | None] = mapped_column(Float)
    change_pct: Mapped[float | None] = mapped_column(Float)
    anomaly_score: Mapped[float | None] = mapped_column(Float)
    severity: Mapped[Severity] = mapped_column(
        Enum(Severity), default=Severity.low, nullable=False
    )
    detection_method: Mapped[str | None] = mapped_column(String(80))
    explanation: Mapped[str | None] = mapped_column(Text)
    status: Mapped[AnomalyStatus] = mapped_column(
        Enum(AnomalyStatus), default=AnomalyStatus.open, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    run: Mapped[AnalysisRun] = relationship("AnalysisRun", back_populates="anomalies")
    alert_history: Mapped[list[AlertHistory]] = relationship(
        "AlertHistory", back_populates="anomaly", cascade="all, delete-orphan"
    )


class AlertHistory(Base):
    __tablename__ = "alert_history"
    __table_args__ = (
        Index("ix_alert_history_anomaly_id", "anomaly_id"),
        Index("ix_alert_history_dedup_key", "dedup_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    anomaly_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("anomalies.id", ondelete="CASCADE"), nullable=False
    )
    recipient: Mapped[str] = mapped_column(String(200), nullable=False)
    dedup_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus), default=AlertStatus.sent, nullable=False
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)

    anomaly: Mapped[Anomaly] = relationship("Anomaly", back_populates="alert_history")
