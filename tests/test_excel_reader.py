"""tests/test_excel_reader.py"""
from __future__ import annotations

import pytest
from pathlib import Path

from src.ingestion.excel_reader import (
    validate_extension,
    validate_size,
    list_sheets,
    read_sheet,
    safe_filename,
    compute_sha256,
)


def test_valid_extension():
    ok, _ = validate_extension("data.xlsx")
    assert ok


def test_invalid_extension():
    ok, msg = validate_extension("data.csv")
    assert not ok
    assert "csv" in msg.lower() or "not supported" in msg.lower()


def test_safe_filename_strips_special_chars():
    result = safe_filename("../../../etc/passwd.xlsx")
    assert ".." not in result
    assert "/" not in result


def test_safe_filename_preserves_extension():
    result = safe_filename("Sales Report 2024.xlsx")
    assert result.endswith(".xlsx")


def test_list_sheets(tmp_xlsx):
    sheets = list_sheets(tmp_xlsx)
    assert isinstance(sheets, list)
    assert len(sheets) >= 1


def test_read_sheet_returns_dataframe(tmp_xlsx):
    import pandas as pd
    df = read_sheet(tmp_xlsx, "Sheet1")
    assert isinstance(df, pd.DataFrame)
    assert not df.empty


def test_read_sheet_correct_columns(tmp_xlsx, sample_df):
    df = read_sheet(tmp_xlsx, "Sheet1")
    for col in sample_df.columns:
        assert col in df.columns


def test_read_sheet_row_count(tmp_xlsx, sample_df):
    df = read_sheet(tmp_xlsx, "Sheet1")
    assert len(df) == len(sample_df)


def test_compute_sha256_is_deterministic(tmp_xlsx):
    h1 = compute_sha256(tmp_xlsx)
    h2 = compute_sha256(tmp_xlsx)
    assert h1 == h2
    assert len(h1) == 64


def test_read_nonexistent_sheet(tmp_xlsx):
    with pytest.raises(ValueError, match="Sheet"):
        read_sheet(tmp_xlsx, "NonExistent_Sheet_XYZABC")
