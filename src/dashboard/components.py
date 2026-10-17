"""
src/dashboard/components.py
Reusable Streamlit UI components.
- No purple gradients, pill buttons, fake metrics, or vibe-coded aesthetics.
- Plain, professional, functional components only.
"""
from __future__ import annotations

import streamlit as st


def metric_card(label: str, value: str, delta: str = "", help_text: str = "") -> None:
    """Render a simple metric card."""
    st.metric(label=label, value=value, delta=delta or None, help=help_text or None)


def severity_badge(severity: str) -> str:
    """Return plain-text severity label (no emoji, no colour HTML)."""
    return f"[{severity.upper()}]"


def alert_banner(message: str, level: str = "info") -> None:
    """Render a Streamlit info/warning/error banner."""
    if level == "error":
        st.error(message)
    elif level == "warning":
        st.warning(message)
    elif level == "success":
        st.success(message)
    else:
        st.info(message)


def empty_state(message: str) -> None:
    st.info(message)


def loading_state(message: str = "Processing..."):
    return st.spinner(message)


def anomaly_table(anomalies: list[dict]) -> None:
    """Render anomalies as a plain table."""
    import pandas as pd

    if not anomalies:
        empty_state("No anomalies to display.")
        return

    rows = []
    for a in anomalies:
        rows.append({
            "Severity": a.get("severity", ""),
            "Metric": a.get("metric_name", ""),
            "Period": a.get("period", ""),
            "Observed": f"{a['observed_value']:,.2f}" if a.get("observed_value") is not None else "N/A",
            "Baseline": f"{a['baseline_value']:,.2f}" if a.get("baseline_value") is not None else "N/A",
            "Change %": f"{a['change_pct']:+.1f}%" if a.get("change_pct") is not None else "N/A",
            "Method": a.get("detection_method", ""),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True)


def section_header(title: str, description: str = "") -> None:
    st.markdown(f"### {title}")
    if description:
        st.caption(description)
    st.divider()
