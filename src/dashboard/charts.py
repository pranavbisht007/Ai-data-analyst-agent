"""
src/dashboard/charts.py
Reusable Plotly chart builders.  All functions accept plain data and
return Plotly figures — no Streamlit calls inside.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

_PALETTE = {
    "primary": "#1B4F72",
    "secondary": "#2E86AB",
    "positive": "#27AE60",
    "negative": "#C0392B",
    "warning": "#F39C12",
    "neutral": "#7F8C8D",
    "background": "#FAFAFA",
    "grid": "#EAECEF",
}

_SEVERITY_COLOR = {
    "Low": "#27AE60",
    "Medium": "#F39C12",
    "High": "#E67E22",
    "Critical": "#C0392B",
}


def _base_layout(title: str = "", height: int = 380) -> dict:
    return dict(
        title=dict(text=title, font=dict(size=15, color=_PALETTE["primary"])),
        plot_bgcolor=_PALETTE["background"],
        paper_bgcolor="white",
        font=dict(family="Inter, Helvetica Neue, sans-serif", size=12, color="#2C3E50"),
        margin=dict(l=50, r=20, t=50, b=50),
        height=height,
        xaxis=dict(showgrid=True, gridcolor=_PALETTE["grid"], linecolor=_PALETTE["grid"]),
        yaxis=dict(showgrid=True, gridcolor=_PALETTE["grid"], linecolor=_PALETTE["grid"]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
    )


def kpi_line_chart(
    df: pd.DataFrame,
    period_col: str,
    value_col: str,
    title: str = "",
    anomaly_periods: Optional[list[str]] = None,
) -> go.Figure:
    """Line chart for a single KPI time series, with optional anomaly markers."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df[period_col],
            y=df[value_col],
            mode="lines+markers",
            name=value_col,
            line=dict(color=_PALETTE["secondary"], width=2),
            marker=dict(size=5),
        )
    )

    if anomaly_periods:
        mask = df[period_col].astype(str).isin(anomaly_periods)
        anomaly_df = df[mask]
        if not anomaly_df.empty:
            fig.add_trace(
                go.Scatter(
                    x=anomaly_df[period_col],
                    y=anomaly_df[value_col],
                    mode="markers",
                    name="Anomaly",
                    marker=dict(
                        color=_PALETTE["negative"],
                        size=10,
                        symbol="circle-open",
                        line=dict(width=2),
                    ),
                )
            )

    fig.update_layout(**_base_layout(title or value_col))
    return fig


def period_comparison_bar(
    current_val: float,
    previous_val: float,
    metric_name: str,
    period_label: str = "Current",
    prev_label: str = "Previous",
) -> go.Figure:
    fig = go.Figure()
    color_curr = _PALETTE["positive"] if current_val >= previous_val else _PALETTE["negative"]
    fig.add_trace(
        go.Bar(x=[prev_label], y=[previous_val], name=prev_label,
               marker_color=_PALETTE["neutral"], width=0.4)
    )
    fig.add_trace(
        go.Bar(x=[period_label], y=[current_val], name=period_label,
               marker_color=color_curr, width=0.4)
    )
    fig.update_layout(**_base_layout(f"{metric_name}: Period Comparison", height=320))
    fig.update_layout(barmode="group")
    return fig


def anomaly_severity_bar(anomaly_counts: dict[str, int]) -> go.Figure:
    """Horizontal bar chart of anomaly counts by severity."""
    severities = ["Critical", "High", "Medium", "Low"]
    counts = [anomaly_counts.get(s, 0) for s in severities]
    colors = [_SEVERITY_COLOR[s] for s in severities]

    fig = go.Figure(
        go.Bar(
            x=counts,
            y=severities,
            orientation="h",
            marker_color=colors,
            text=counts,
            textposition="outside",
        )
    )
    fig.update_layout(**_base_layout("Anomalies by Severity", height=280))
    return fig


def rolling_avg_chart(
    df: pd.DataFrame,
    period_col: str,
    value_col: str,
    window: int = 3,
    title: str = "",
) -> go.Figure:
    df = df.copy()
    df["_rolling"] = df[value_col].rolling(window=window, min_periods=1).mean()
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df[period_col], y=df[value_col],
            mode="lines", name="Actual",
            line=dict(color=_PALETTE["neutral"], width=1.5, dash="dot"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df[period_col], y=df["_rolling"],
            mode="lines", name=f"{window}-period avg",
            line=dict(color=_PALETTE["secondary"], width=2),
        )
    )
    fig.update_layout(**_base_layout(title or f"{value_col} with {window}-period Rolling Average"))
    return fig


def multi_kpi_line(
    dfs: dict[str, pd.DataFrame],
    period_col: str,
) -> go.Figure:
    """Overlay multiple KPI time series on one chart."""
    colors = [
        _PALETTE["secondary"], _PALETTE["positive"], _PALETTE["warning"],
        _PALETTE["negative"], _PALETTE["primary"], _PALETTE["neutral"],
    ]
    fig = go.Figure()
    for idx, (name, df) in enumerate(dfs.items()):
        fig.add_trace(
            go.Scatter(
                x=df[period_col], y=df[name],
                mode="lines+markers", name=name,
                line=dict(color=colors[idx % len(colors)], width=2),
                marker=dict(size=4),
            )
        )
    fig.update_layout(**_base_layout("KPI Trends Overview"))
    return fig
