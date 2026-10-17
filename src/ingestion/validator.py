"""
src/ingestion/validator.py
Data validation and profiling.  Returns structured results; never modifies
the original DataFrame passed in.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.is_valid = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def add_info(self, msg: str) -> None:
        self.info.append(msg)


@dataclass
class DataProfile:
    row_count: int = 0
    col_count: int = 0
    column_types: dict[str, str] = field(default_factory=dict)
    missing_counts: dict[str, int] = field(default_factory=dict)
    duplicate_row_count: int = 0
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    numeric_columns: list[str] = field(default_factory=list)
    date_candidates: list[str] = field(default_factory=list)
    summary_stats: dict[str, dict] = field(default_factory=dict)


def validate_dataframe(
    df: pd.DataFrame,
    date_col: Optional[str] = None,
    kpi_cols: Optional[list[str]] = None,
) -> ValidationResult:
    result = ValidationResult()

    if df.empty:
        result.add_error("The dataset is empty.")
        return result

    # ── Duplicate rows ────────────────────────────────────────────────────────
    dup_count = df.duplicated().sum()
    if dup_count > 0:
        result.add_warning(f"{dup_count} duplicate row(s) detected. They will be included in analysis unless removed.")

    # ── Missing values ────────────────────────────────────────────────────────
    for col in df.columns:
        miss = int(df[col].isna().sum())
        if miss > 0:
            pct = miss / len(df) * 100
            msg = f"Column '{col}': {miss} missing value(s) ({pct:.1f}%)."
            if pct > 50:
                result.add_error(f"{msg} Over 50% missing — this column may not be usable.")
            else:
                result.add_warning(msg)

    # ── Date column checks ────────────────────────────────────────────────────
    if date_col:
        if date_col not in df.columns:
            result.add_error(f"Date column '{date_col}' not found in dataset.")
        else:
            parsed = pd.to_datetime(df[date_col], errors="coerce")
            bad = parsed.isna().sum()
            if bad > 0:
                result.add_warning(
                    f"Date column '{date_col}': {bad} value(s) could not be parsed as dates."
                )
            if parsed.notna().sum() < 2:
                result.add_error(
                    f"Date column '{date_col}' has fewer than 2 valid dates. Cannot compute time-series metrics."
                )

    # ── KPI column checks ─────────────────────────────────────────────────────
    if kpi_cols:
        for col in kpi_cols:
            if col not in df.columns:
                result.add_error(f"KPI column '{col}' not found in dataset.")
                continue
            numeric = pd.to_numeric(df[col], errors="coerce")
            bad = numeric.isna().sum()
            if bad > 0:
                result.add_warning(
                    f"KPI column '{col}': {bad} non-numeric value(s) detected."
                )
            if (numeric < 0).any():
                result.add_info(
                    f"KPI column '{col}' contains negative values. Verify whether this is expected."
                )

    result.add_info(f"Dataset has {len(df)} rows and {len(df.columns)} columns.")
    return result


def profile_dataframe(df: pd.DataFrame, date_col: Optional[str] = None) -> DataProfile:
    profile = DataProfile(
        row_count=len(df),
        col_count=len(df.columns),
        duplicate_row_count=int(df.duplicated().sum()),
    )

    for col in df.columns:
        profile.column_types[col] = str(df[col].dtype)
        profile.missing_counts[col] = int(df[col].isna().sum())

    # Detect numeric columns
    profile.numeric_columns = [
        c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])
    ]

    # Detect date candidates (columns with "date" or "time" in name, or parseable)
    for col in df.columns:
        name_lower = col.lower()
        if any(kw in name_lower for kw in ("date", "time", "period", "month", "week", "day", "year")):
            profile.date_candidates.append(col)
            continue
        if not pd.api.types.is_numeric_dtype(df[col]):
            sample = df[col].dropna().head(20)
            parsed = pd.to_datetime(sample, errors="coerce")
            if parsed.notna().sum() >= len(sample) * 0.8:
                profile.date_candidates.append(col)

    # Date range
    if date_col and date_col in df.columns:
        parsed = pd.to_datetime(df[date_col], errors="coerce").dropna()
        if not parsed.empty:
            profile.date_range_start = str(parsed.min().date())
            profile.date_range_end = str(parsed.max().date())

    # Summary stats for numeric columns
    for col in profile.numeric_columns:
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if series.empty:
            continue
        profile.summary_stats[col] = {
            "count": int(series.count()),
            "sum": float(series.sum()),
            "mean": float(series.mean()),
            "median": float(series.median()),
            "std": float(series.std()) if len(series) > 1 else 0.0,
            "min": float(series.min()),
            "max": float(series.max()),
        }

    return profile
