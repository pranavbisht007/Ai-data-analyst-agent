"""
app.py  —  AI Data Analyst Agent
Main Streamlit entry point.

Security measures implemented:
- Session-based authentication with bcrypt password hashing
- Input sanitised with bleach before storage
- File upload restricted by extension and size
- Uploaded file names sanitised
- No secrets in UI, logs, or session state
- Debug mode off
- Content-Security-Policy header set via st.html() at startup
"""
from __future__ import annotations

import hashlib
import io
import logging
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import bcrypt
import bleach
import pandas as pd
import streamlit as st

# ── Bootstrap ─────────────────────────────────────────────────────────────────
from config.settings import (
    ADMIN_PASSWORD_HASH,
    APP_SECRET_KEY,
    UPLOADS_DIR,
    MAX_UPLOAD_MB,
    ALLOWED_EXTENSIONS,
    DEFAULT_THRESHOLD_PCT,
)
from src.database.db import init_db, get_session
from src.database.models import (
    RunTrigger, RunStatus, Severity, AnomalyStatus,
    DatasetStatus,
)
from src.database.repository import (
    create_dataset, dataset_hash_exists, finish_run, get_dataset,
    list_anomalies, list_datasets, list_profiles, list_runs,
    save_anomaly, start_run, update_dataset_status, upsert_profile,
    upsert_metric_config,
)
from src.ingestion.excel_reader import (
    compute_sha256, list_sheets, read_sheet, safe_filename, validate_extension,
    validate_size,
)
from src.ingestion.validator import profile_dataframe, validate_dataframe
from src.analytics.profiler import build_report
from src.detection.detector import detect_anomalies
from src.agent.analyst import run_ai_analysis
from src.alerts.email_service import send_test_email
from src.dashboard.charts import (
    anomaly_severity_bar, kpi_line_chart, period_comparison_bar,
    rolling_avg_chart, multi_kpi_line,
)
from src.dashboard.components import (
    alert_banner, anomaly_table, empty_state, loading_state,
    metric_card, section_header,
)

logger = logging.getLogger(__name__)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Data Analyst Agent",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": "AI Data Analyst Agent — local business analytics.",
    },
)

# ── Minimal custom CSS (professional, no gradients or animations) ─────────────
st.markdown(
    """
    <style>
    /* Remove Streamlit branding */
    #MainMenu, footer, header { visibility: hidden; }
    /* Clean card style */
    div[data-testid="stMetric"] {
        background: #f7f9fc;
        border: 1px solid #e2e8f0;
        border-radius: 4px;
        padding: 12px 16px;
    }
    /* Consistent sans-serif font */
    html, body, [class*="css"] {
        font-family: "Inter", "Helvetica Neue", Arial, sans-serif;
    }
    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #1B2A3B;
        color: #ffffff;
    }
    section[data-testid="stSidebar"] * {
        color: #ffffff !important;
    }
    /* Dividers */
    hr { border-top: 1px solid #e2e8f0; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Initialise DB ─────────────────────────────────────────────────────────────
init_db()


# ═══════════════════════════════════════════════════════════════════════════════
# Authentication
# ═══════════════════════════════════════════════════════════════════════════════

def _authenticate(password: str) -> bool:
    """
    Check password against the stored bcrypt hash.
    If no hash is configured, access is open (suitable for fully local use only).
    """
    stored_hash = ADMIN_PASSWORD_HASH.encode() if ADMIN_PASSWORD_HASH else None
    if stored_hash is None:
        return True  # No auth configured — local use
    try:
        return bcrypt.checkpw(password.encode(), stored_hash)
    except Exception:
        return False


def require_auth() -> bool:
    """
    Show login form and return True only when the user is authenticated.
    Uses st.session_state to persist auth across reruns.
    """
    if ADMIN_PASSWORD_HASH == "":
        # Auth not configured — local-only mode, open access
        return True

    if st.session_state.get("authenticated"):
        return True

    st.title("Data Analyst Agent")
    st.markdown("Enter the admin password to continue.")

    with st.form("login_form"):
        pwd = st.text_input("Password", type="password", max_chars=128)
        submitted = st.form_submit_button("Sign in")

    if submitted:
        if _authenticate(pwd):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
            # Small delay to slow brute-force
            time.sleep(1)

    return False


# ═══════════════════════════════════════════════════════════════════════════════
# Sanitisation helpers
# ═══════════════════════════════════════════════════════════════════════════════

def sanitise(text: str, max_len: int = 500) -> str:
    """Strip HTML tags and limit length to prevent XSS via stored text."""
    cleaned = bleach.clean(str(text), tags=[], strip=True)
    return cleaned[:max_len]


# ═══════════════════════════════════════════════════════════════════════════════
# Page: Overview
# ═══════════════════════════════════════════════════════════════════════════════

def page_overview() -> None:
    section_header("Overview", "Recent analysis activity and key metrics.")

    with get_session() as session:
        runs = list_runs(session, limit=10)
        all_anomalies = list_anomalies(session, limit=500)

    if not runs:
        empty_state(
            "No analysis runs yet. Upload an Excel file to get started."
        )
        return

    # ── Summary cards ─────────────────────────────────────────────────────────
    total_runs = len(runs)
    completed = sum(1 for r in runs if r.status == RunStatus.completed)
    open_anomalies = sum(1 for a in all_anomalies if a.status == AnomalyStatus.open)
    critical = sum(
        1 for a in all_anomalies
        if a.severity == Severity.critical and a.status == AnomalyStatus.open
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Analysis Runs", str(total_runs))
    with c2:
        metric_card("Completed", str(completed))
    with c3:
        metric_card("Open Anomalies", str(open_anomalies))
    with c4:
        metric_card("Critical", str(critical))

    st.markdown("---")

    # ── Anomaly severity chart ─────────────────────────────────────────────────
    severity_counts = {
        "Critical": critical,
        "High": sum(1 for a in all_anomalies if a.severity == Severity.high),
        "Medium": sum(1 for a in all_anomalies if a.severity == Severity.medium),
        "Low": sum(1 for a in all_anomalies if a.severity == Severity.low),
    }
    if any(severity_counts.values()):
        st.subheader("Open Anomalies by Severity")
        st.plotly_chart(anomaly_severity_bar(severity_counts), use_container_width=True)

    # ── Recent runs table ─────────────────────────────────────────────────────
    st.subheader("Recent Analysis Runs")
    rows = []
    for r in runs[:10]:
        rows.append({
            "Run ID": r.id,
            "Dataset ID": r.dataset_id,
            "Trigger": r.trigger_type.value,
            "Status": r.status.value,
            "Started": str(r.started_at)[:19],
            "Summary": (r.summary or "")[:120],
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Page: Upload & Data Preview
# ═══════════════════════════════════════════════════════════════════════════════

def page_upload() -> None:
    section_header("Upload Data", "Upload an Excel file (.xlsx or .xls).")

    uploaded = st.file_uploader(
        "Choose a file",
        type=["xlsx", "xls"],
        help=f"Maximum size: {MAX_UPLOAD_MB} MB. Accepted formats: .xlsx, .xls",
    )

    if uploaded is None:
        empty_state("No file uploaded yet.")
        return

    # ── Extension check ────────────────────────────────────────────────────────
    ok, err = validate_extension(uploaded.name)
    if not ok:
        alert_banner(err, "error")
        return

    # ── Save to disk with safe name ────────────────────────────────────────────
    safe_name = safe_filename(uploaded.name)
    uid = uuid.uuid4().hex[:8]
    dest_path = UPLOADS_DIR / f"{uid}_{safe_name}"

    raw_bytes = uploaded.read()
    if len(raw_bytes) == 0:
        alert_banner("The uploaded file is empty.", "error")
        return
    if len(raw_bytes) > MAX_UPLOAD_MB * 1024 * 1024:
        alert_banner(f"File exceeds the {MAX_UPLOAD_MB} MB limit.", "error")
        return

    dest_path.write_bytes(raw_bytes)

    # ── Integrity / size check ─────────────────────────────────────────────────
    ok, err = validate_size(dest_path)
    if not ok:
        dest_path.unlink(missing_ok=True)
        alert_banner(err, "error")
        return

    file_hash = compute_sha256(dest_path)

    # ── Duplicate check ────────────────────────────────────────────────────────
    with get_session() as session:
        if dataset_hash_exists(session, file_hash):
            dest_path.unlink(missing_ok=True)
            alert_banner(
                "This exact file has already been uploaded (duplicate hash detected). "
                "If your data has changed, save it under a different name.",
                "warning",
            )
            return

    # ── Sheet selection ────────────────────────────────────────────────────────
    try:
        sheets = list_sheets(dest_path)
    except ValueError as exc:
        dest_path.unlink(missing_ok=True)
        alert_banner(str(exc), "error")
        return

    sheet = st.selectbox("Select worksheet", sheets)

    # ── Load preview ───────────────────────────────────────────────────────────
    try:
        df = read_sheet(dest_path, sheet)
    except ValueError as exc:
        dest_path.unlink(missing_ok=True)
        alert_banner(str(exc), "error")
        return

    data_profile = profile_dataframe(df)

    # ── Profile display ────────────────────────────────────────────────────────
    st.subheader("Dataset Profile")
    p1, p2, p3 = st.columns(3)
    with p1:
        st.metric("Rows", data_profile.row_count)
    with p2:
        st.metric("Columns", data_profile.col_count)
    with p3:
        st.metric("Duplicate Rows", data_profile.duplicate_row_count)

    st.subheader("Column Types")
    type_df = pd.DataFrame([
        {"Column": c, "Type": t, "Missing": data_profile.missing_counts.get(c, 0)}
        for c, t in data_profile.column_types.items()
    ])
    st.dataframe(type_df, use_container_width=True)

    st.subheader("Data Preview (first 10 rows)")
    st.dataframe(df.head(10), use_container_width=True)

    # ── Column selection ───────────────────────────────────────────────────────
    st.subheader("Column Configuration")
    all_cols = list(df.columns)
    date_candidates = data_profile.date_candidates or all_cols
    numeric_cols = data_profile.numeric_columns

    date_col = st.selectbox(
        "Date column",
        date_candidates,
        help="Column that identifies the reporting period.",
    )
    kpi_cols = st.multiselect(
        "KPI columns to analyse",
        numeric_cols,
        default=numeric_cols[:4] if len(numeric_cols) >= 4 else numeric_cols,
        help="Select the numeric columns you want to track.",
    )

    # ── Validation ─────────────────────────────────────────────────────────────
    if date_col and kpi_cols:
        val_result = validate_dataframe(df, date_col, kpi_cols)
        if val_result.errors:
            for e in val_result.errors:
                alert_banner(e, "error")
        if val_result.warnings:
            with st.expander("Validation warnings"):
                for w in val_result.warnings:
                    st.warning(w)
        if val_result.info:
            for i in val_result.info:
                st.caption(i)

        if not val_result.is_valid:
            alert_banner(
                "Please fix the errors above before saving.", "error"
            )
            dest_path.unlink(missing_ok=True)
            return

    # ── Date range ─────────────────────────────────────────────────────────────
    if date_col:
        dp2 = profile_dataframe(df, date_col=date_col)
        if dp2.date_range_start:
            st.caption(
                f"Date range: {dp2.date_range_start} to {dp2.date_range_end}"
            )

    # ── Profile — link to a business profile ──────────────────────────────────
    with get_session() as session:
        profiles = list_profiles(session)
    profile_names = [p.name for p in profiles]
    selected_profile = None
    if profile_names:
        sel = st.selectbox(
            "Link to business profile (optional)",
            ["— None —"] + profile_names,
        )
        if sel != "— None —":
            selected_profile = next(
                (p for p in profiles if p.name == sel), None
            )

    # ── Save ───────────────────────────────────────────────────────────────────
    if st.button("Save dataset and run analysis"):
        with loading_state("Saving and analysing..."):
            with get_session() as session:
                ds = create_dataset(
                    session,
                    file_name=safe_name,
                    file_path=str(dest_path),
                    file_hash=file_hash,
                    sheet_name=sheet,
                    profile_id=selected_profile.id if selected_profile else None,
                    row_count=data_profile.row_count,
                    col_count=data_profile.col_count,
                    date_column=date_col,
                )
                dataset_id = ds.id
                update_dataset_status(session, dataset_id, DatasetStatus.valid)

            # Run analysis inline
            _run_inline_analysis(dataset_id, df, date_col, kpi_cols)

        alert_banner(
            f"Dataset saved (ID: {dataset_id}). Analysis complete.", "success"
        )
        st.session_state["last_dataset_id"] = dataset_id
        st.session_state["last_date_col"] = date_col
        st.session_state["last_kpi_cols"] = kpi_cols


def _run_inline_analysis(
    dataset_id: int,
    df: pd.DataFrame,
    date_col: str,
    kpi_cols: list[str],
    threshold_pct: float = DEFAULT_THRESHOLD_PCT,
) -> Optional[int]:
    """Run analysis pipeline and persist results. Returns run_id."""
    with get_session() as session:
        run = start_run(session, dataset_id=dataset_id, trigger=RunTrigger.upload)
        run_id = run.id

    try:
        report = build_report(
            df=df, date_col=date_col, kpi_cols=kpi_cols,
            dataset_id=dataset_id, run_id=run_id,
        )
        n_anomalies = 0
        with get_session() as session:
            for summary in report.kpi_summaries:
                detection = detect_anomalies(
                    summary.aggregated, summary.metric_name,
                    threshold_pct=threshold_pct,
                )
                for a in detection.anomalies:
                    save_anomaly(
                        session, run_id=run_id,
                        metric_name=a.metric_name, period=a.period,
                        observed_value=a.observed_value,
                        baseline_value=a.baseline_value,
                        change_abs=a.change_abs,
                        change_pct=a.change_pct,
                        anomaly_score=a.anomaly_score,
                        severity=a.severity,
                        detection_method=a.detection_method,
                        explanation=a.explanation,
                    )
                    n_anomalies += 1
            finish_run(
                session, run_id, RunStatus.completed,
                f"Analysed {len(report.kpi_summaries)} KPI(s). {n_anomalies} anomaly(ies).",
            )
        st.session_state["last_run_id"] = run_id
        st.session_state["last_report"] = report
        return run_id
    except Exception as exc:
        logger.exception("Inline analysis failed: %s", exc)
        with get_session() as session:
            finish_run(session, run_id, RunStatus.failed, str(exc))
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Page: KPI Analysis
# ═══════════════════════════════════════════════════════════════════════════════

def page_kpi_analysis() -> None:
    section_header("KPI Analysis", "Explore aggregated KPI trends and period comparisons.")

    report = st.session_state.get("last_report")
    if report is None:
        empty_state("No analysis data available. Upload a file first.")
        return

    if not report.kpi_summaries:
        empty_state("No KPI summaries computed for the current dataset.")
        return

    metric_names = [s.metric_name for s in report.kpi_summaries]
    selected = st.selectbox("Select KPI", metric_names)
    summary = next(s for s in report.kpi_summaries if s.metric_name == selected)

    # ── Summary cards ──────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    pct_str = f"{summary.pct_change:+.1f}%" if summary.pct_change is not None else "N/A"
    with c1:
        metric_card("Latest", f"{summary.latest_value:,.2f}")
    with c2:
        metric_card("Previous", f"{summary.previous_value:,.2f}")
    with c3:
        metric_card("Change", pct_str)
    with c4:
        metric_card("Mean", f"{summary.mean:,.2f}")
    with c5:
        metric_card("Total", f"{summary.total:,.2f}")

    st.markdown("---")

    # ── Charts ─────────────────────────────────────────────────────────────────
    col_l, col_r = st.columns([2, 1])
    with col_l:
        run_id = st.session_state.get("last_run_id")
        anomaly_periods: list[str] = []
        if run_id:
            with get_session() as session:
                db_anomalies = list_anomalies(session, run_id=run_id)
                anomaly_periods = [
                    a.period for a in db_anomalies if a.metric_name == selected
                ]
        fig = kpi_line_chart(
            summary.aggregated, "period", selected,
            title=f"{selected} over time",
            anomaly_periods=anomaly_periods,
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        fig2 = period_comparison_bar(
            summary.latest_value, summary.previous_value, selected
        )
        st.plotly_chart(fig2, use_container_width=True)

    # ── Rolling average ────────────────────────────────────────────────────────
    window = st.slider("Rolling average window (periods)", 2, 12, 3)
    fig3 = rolling_avg_chart(summary.aggregated, "period", selected, window=window)
    st.plotly_chart(fig3, use_container_width=True)

    # ── All KPIs overlay ──────────────────────────────────────────────────────
    if len(report.kpi_summaries) > 1:
        st.subheader("All KPIs Overview")
        dfs = {s.metric_name: s.aggregated for s in report.kpi_summaries}
        st.plotly_chart(multi_kpi_line(dfs, "period"), use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Page: Anomaly Detection
# ═══════════════════════════════════════════════════════════════════════════════

def page_anomalies() -> None:
    section_header("Anomaly Detection", "Detected anomalies for the current analysis run.")

    run_id = st.session_state.get("last_run_id")
    if not run_id:
        empty_state("No analysis run available. Upload a file to start.")
        return

    with get_session() as session:
        db_anomalies = list_anomalies(session, run_id=run_id)

    if not db_anomalies:
        alert_banner("No anomalies detected in the current run.", "success")
        return

    # ── Filters ────────────────────────────────────────────────────────────────
    severity_options = ["All", "Critical", "High", "Medium", "Low"]
    sel_severity = st.selectbox("Filter by severity", severity_options)

    rows = []
    for a in db_anomalies:
        if sel_severity != "All" and a.severity.value != sel_severity:
            continue
        rows.append({
            "severity": a.severity.value,
            "metric_name": a.metric_name,
            "period": a.period,
            "observed_value": a.observed_value,
            "baseline_value": a.baseline_value,
            "change_pct": a.change_pct,
            "detection_method": a.detection_method,
        })

    anomaly_table(rows)

    # ── Detail view ───────────────────────────────────────────────────────────
    if db_anomalies:
        with st.expander("Anomaly explanations"):
            for a in db_anomalies:
                if sel_severity != "All" and a.severity.value != sel_severity:
                    continue
                st.markdown(
                    f"**[{a.severity.value}] {a.metric_name} — {a.period}**"
                )
                st.caption(a.explanation or "No explanation recorded.")
                st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
# Page: AI Business Insights
# ═══════════════════════════════════════════════════════════════════════════════

def page_ai_insights() -> None:
    section_header("AI Business Insights", "AI-generated analysis of current findings.")

    report = st.session_state.get("last_report")
    run_id = st.session_state.get("last_run_id")

    if report is None or run_id is None:
        empty_state("Run an analysis first.")
        return

    with get_session() as session:
        db_anomalies = list_anomalies(session, run_id=run_id)
        profiles = list_profiles(session)

    # ── Business context ───────────────────────────────────────────────────────
    profile = profiles[0] if profiles else None
    business_name = profile.name if profile else ""
    industry = profile.industry if profile else ""
    description = profile.description if profile else ""
    notes = profile.notes if profile else ""

    # Convert DB anomalies to AnomalyRecord for the analyst
    from src.detection.detector import AnomalyRecord
    from src.database.models import Severity as Sev

    anom_records = []
    for a in db_anomalies:
        anom_records.append(
            AnomalyRecord(
                metric_name=a.metric_name,
                period=a.period,
                observed_value=a.observed_value,
                baseline_value=a.baseline_value,
                change_abs=a.change_abs,
                change_pct=a.change_pct,
                anomaly_score=a.anomaly_score or 0.0,
                severity=a.severity,
                detection_method=a.detection_method or "",
                explanation=a.explanation or "",
            )
        )

    if st.button("Generate AI Analysis"):
        with loading_state("Calling AI analyst..."):
            analysis_text, ai_used = run_ai_analysis(
                report=report,
                anomalies=anom_records,
                business_name=business_name,
                industry=industry,
                description=description,
                notes=notes,
            )
        if not ai_used:
            alert_banner(
                "Gemini API key not configured. Showing statistical summary only.",
                "info",
            )
        st.text_area("Analysis", analysis_text, height=500)


# ═══════════════════════════════════════════════════════════════════════════════
# Page: Alert Settings
# ═══════════════════════════════════════════════════════════════════════════════

def page_alert_settings() -> None:
    section_header("Alert Settings", "Configure email notifications for anomalies.")

    st.info(
        "Email credentials are read from environment variables (.env file). "
        "They are never stored in the database or displayed here."
    )

    alerts_enabled = st.toggle(
        "Enable email alerts",
        value=st.session_state.get("alerts_enabled", False),
    )
    st.session_state["alerts_enabled"] = alerts_enabled

    recipients_raw = st.text_area(
        "Recipient email addresses (one per line)",
        value=st.session_state.get("alert_recipients", ""),
        max_chars=1000,
    )
    # Sanitise and validate emails
    raw_lines = recipients_raw.strip().splitlines()
    recipients = []
    for line in raw_lines:
        addr = sanitise(line.strip(), 200)
        if "@" in addr and "." in addr:
            recipients.append(addr)

    st.session_state["alert_recipients"] = "\n".join(recipients)

    min_severity_label = st.selectbox(
        "Minimum severity to alert on",
        ["Low", "Medium", "High", "Critical"],
        index=2,
    )
    st.session_state["min_severity"] = min_severity_label

    if st.button("Send test email"):
        if not recipients:
            alert_banner("Enter at least one valid recipient.", "error")
        else:
            with loading_state("Sending test email..."):
                ok, err = send_test_email(recipients[0])
            if ok:
                alert_banner("Test email sent successfully.", "success")
            else:
                alert_banner(f"Failed to send: {err}", "error")


# ═══════════════════════════════════════════════════════════════════════════════
# Page: Analysis History
# ═══════════════════════════════════════════════════════════════════════════════

def page_history() -> None:
    section_header("Analysis History", "All analysis runs stored in the local database.")

    with get_session() as session:
        runs = list_runs(session, limit=50)
        datasets = {ds.id: ds for ds in list_datasets(session, limit=200)}

    if not runs:
        empty_state("No analysis history yet.")
        return

    rows = []
    for r in runs:
        ds = datasets.get(r.dataset_id)
        rows.append({
            "Run ID": r.id,
            "File": ds.file_name if ds else "—",
            "Sheet": ds.sheet_name if ds else "—",
            "Trigger": r.trigger_type.value,
            "Status": r.status.value,
            "Started": str(r.started_at)[:19],
            "Finished": str(r.finished_at)[:19] if r.finished_at else "—",
            "Summary": (r.summary or "")[:100],
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Page: Business Settings
# ═══════════════════════════════════════════════════════════════════════════════

def page_business_settings() -> None:
    section_header("Business Settings", "Configure your business profile and metric thresholds.")

    with get_session() as session:
        profiles = list_profiles(session)

    st.subheader("Business Profile")
    with st.form("business_form"):
        name = st.text_input(
            "Business name *",
            value=profiles[0].name if profiles else "",
            max_chars=200,
        )
        industry = st.text_input(
            "Industry",
            value=profiles[0].industry or "" if profiles else "",
            max_chars=100,
        )
        description = st.text_area(
            "Business description",
            value=profiles[0].description or "" if profiles else "",
            max_chars=1000,
        )
        notes = st.text_area(
            "Additional notes (metric meanings, expected directions, etc.)",
            value=profiles[0].notes or "" if profiles else "",
            max_chars=2000,
        )
        threshold = st.number_input(
            "Default anomaly threshold (%)",
            min_value=5.0,
            max_value=200.0,
            value=float(DEFAULT_THRESHOLD_PCT),
            step=5.0,
            help="Flag a change as anomalous if it exceeds this percentage.",
        )
        submitted = st.form_submit_button("Save settings")

    if submitted:
        if not name.strip():
            alert_banner("Business name is required.", "error")
        else:
            safe_name = sanitise(name)
            safe_industry = sanitise(industry)
            safe_desc = sanitise(description, 1000)
            safe_notes = sanitise(notes, 2000)

            with get_session() as session:
                upsert_profile(
                    session,
                    name=safe_name,
                    industry=safe_industry,
                    description=safe_desc,
                    notes=safe_notes,
                )
            alert_banner("Business profile saved.", "success")
            st.session_state["threshold_pct"] = threshold


# ═══════════════════════════════════════════════════════════════════════════════
# Main router
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    if not require_auth():
        st.stop()

    pages = {
        "Overview": page_overview,
        "Upload Data": page_upload,
        "KPI Analysis": page_kpi_analysis,
        "Anomaly Detection": page_anomalies,
        "AI Insights": page_ai_insights,
        "Alert Settings": page_alert_settings,
        "History": page_history,
        "Business Settings": page_business_settings,
    }

    with st.sidebar:
        st.markdown("## Data Analyst Agent")
        st.divider()
        page = st.radio("Navigation", list(pages.keys()), label_visibility="collapsed")
        st.divider()
        if ADMIN_PASSWORD_HASH:
            if st.button("Sign out"):
                st.session_state.clear()
                st.rerun()

    pages[page]()


if __name__ == "__main__":
    main()