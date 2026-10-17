"""
tests/conftest.py
Shared pytest fixtures.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pandas as pd
import pytest

# Ensure the project root is on the path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Use an in-memory SQLite DB for tests
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-not-for-production-1234567890")
os.environ.setdefault("ADMIN_PASSWORD_HASH", "")


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Clean monthly time-series DataFrame with known values."""
    dates = pd.date_range("2024-01-01", periods=18, freq="MS")
    revenue = [
        100_000, 102_000, 98_000, 105_000, 107_000, 110_000,
        108_000, 112_000, 115_000, 60_000,  # intentional drop at index 9
        118_000, 120_000, 122_000, 119_000, 125_000, 200_000,  # spike at 15
        130_000, 128_000,
    ]
    orders = [
        500, 510, 495, 520, 530, 545,
        540, 555, 560, 300,  # drop
        575, 580, 590, 585, 600, 950,  # spike
        620, 615,
    ]
    expenses = [
        60_000, 61_000, 59_500, 62_000, 63_000, 64_500,
        63_000, 65_000, 66_000, 67_000,
        68_000, 69_000, 70_000, 71_000, 72_000, 73_000,
        74_000, 75_000,
    ]
    visitors = [
        10_000, 10_200, 9_800, 10_500, 10_700, 11_000,
        10_800, 11_200, 11_500, 11_000,
        11_800, 30_000,  # spike at index 11
        12_200, 11_900, 12_500, 13_000,
        13_000, 12_800,
    ]
    return pd.DataFrame({
        "date": dates,
        "revenue": revenue,
        "orders": orders,
        "expenses": expenses,
        "website_visitors": visitors,
    })


@pytest.fixture
def tmp_xlsx(sample_df, tmp_path) -> Path:
    """Write sample_df to a temporary .xlsx file."""
    p = tmp_path / "sample.xlsx"
    sample_df.to_excel(p, index=False)
    return p
