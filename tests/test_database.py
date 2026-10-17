"""tests/test_database.py — DB model relationships and repository functions."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, BusinessProfile, Dataset, AnalysisRun, Anomaly, Severity
from src.database.repository import (
    create_dataset,
    dataset_hash_exists,
    finish_run,
    list_anomalies,
    list_profiles,
    list_runs,
    save_anomaly,
    start_run,
    update_dataset_status,
    upsert_profile,
    DatasetStatus,
    RunStatus,
    RunTrigger,
)


@pytest.fixture
def db_session():
    """In-memory SQLite session for isolation."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _fk(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_upsert_profile_creates(db_session):
    profile = upsert_profile(db_session, name="Acme Corp", industry="Retail")
    db_session.commit()
    assert profile.id is not None
    assert profile.name == "Acme Corp"


def test_upsert_profile_updates(db_session):
    upsert_profile(db_session, name="Acme Corp", industry="Retail")
    db_session.commit()
    upsert_profile(db_session, name="Acme Corp", industry="E-commerce")
    db_session.commit()
    profiles = list_profiles(db_session)
    assert len(profiles) == 1
    assert profiles[0].industry == "E-commerce"


def test_create_dataset(db_session):
    ds = create_dataset(
        db_session,
        file_name="sales.xlsx",
        file_path="/tmp/sales.xlsx",
        file_hash="abc123",
    )
    db_session.commit()
    assert ds.id is not None
    assert ds.status == DatasetStatus.pending


def test_dataset_hash_exists(db_session):
    create_dataset(db_session, file_name="f.xlsx", file_path="/p", file_hash="hash1")
    db_session.commit()
    assert dataset_hash_exists(db_session, "hash1") is True
    assert dataset_hash_exists(db_session, "unknown") is False


def test_start_and_finish_run(db_session):
    ds = create_dataset(db_session, file_name="f.xlsx", file_path="/p", file_hash="h2")
    db_session.commit()
    run = start_run(db_session, dataset_id=ds.id, trigger=RunTrigger.manual)
    db_session.commit()
    assert run.id is not None

    finish_run(db_session, run.id, RunStatus.completed, "Done")
    db_session.commit()
    runs = list_runs(db_session, dataset_id=ds.id)
    assert runs[0].status == RunStatus.completed
    assert runs[0].summary == "Done"


def test_save_and_list_anomaly(db_session):
    ds = create_dataset(db_session, file_name="f.xlsx", file_path="/p", file_hash="h3")
    db_session.commit()
    run = start_run(db_session, dataset_id=ds.id)
    db_session.commit()

    a = save_anomaly(
        db_session,
        run_id=run.id,
        metric_name="revenue",
        period="2024-10-01",
        observed_value=60_000,
        baseline_value=115_000,
        change_abs=-55_000,
        change_pct=-47.8,
        anomaly_score=47.8,
        severity=Severity.critical,
        detection_method="percentage_change_threshold",
        explanation="Revenue dropped 47.8%.",
    )
    db_session.commit()
    anomalies = list_anomalies(db_session, run_id=run.id)
    assert len(anomalies) == 1
    assert anomalies[0].metric_name == "revenue"
    assert anomalies[0].severity == Severity.critical


def test_foreign_key_cascade_delete(db_session):
    """Deleting a run should delete its anomalies (cascade)."""
    ds = create_dataset(db_session, file_name="f.xlsx", file_path="/p", file_hash="h4")
    db_session.commit()
    run = start_run(db_session, dataset_id=ds.id)
    db_session.commit()
    save_anomaly(
        db_session, run_id=run.id, metric_name="rev", period="2024-01",
        observed_value=1, baseline_value=2, change_abs=-1, change_pct=-50.0,
        anomaly_score=50.0, severity=Severity.high,
        detection_method="pct", explanation="test",
    )
    db_session.commit()

    db_session.delete(run)
    db_session.commit()
    anomalies = list_anomalies(db_session, run_id=run.id)
    assert len(anomalies) == 0
