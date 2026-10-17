"""
src/ingestion/excel_reader.py
Safe Excel file reading.  Never executes spreadsheet formulas or macros.
"""
from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Optional

import pandas as pd

from config.settings import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES

logger = logging.getLogger(__name__)

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_\-.]")


def safe_filename(name: str) -> str:
    """Return a filesystem-safe version of a file name."""
    stem = Path(name).stem
    suffix = Path(name).suffix.lower()
    safe_stem = _SAFE_NAME_RE.sub("_", stem)[:120]
    return f"{safe_stem}{suffix}"


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65_536), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_extension(file_name: str) -> tuple[bool, str]:
    ext = Path(file_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"File type '{ext}' is not supported. Accepted: {', '.join(ALLOWED_EXTENSIONS)}."
    return True, ""


def validate_size(path: Path) -> tuple[bool, str]:
    size = path.stat().st_size
    if size == 0:
        return False, "The uploaded file is empty."
    if size > MAX_UPLOAD_BYTES:
        mb = size / (1024 * 1024)
        return False, f"File is {mb:.1f} MB, which exceeds the {MAX_UPLOAD_BYTES // (1024*1024)} MB limit."
    return True, ""


def list_sheets(path: Path) -> list[str]:
    """Return worksheet names without loading data."""
    try:
        xl = pd.ExcelFile(path, engine=_pick_engine(path))
        return xl.sheet_names
    except Exception as exc:
        raise ValueError(f"Cannot open workbook: {exc}") from exc


def _pick_engine(path: Path) -> str:
    return "xlrd" if path.suffix.lower() == ".xls" else "openpyxl"


def read_sheet(
    path: Path,
    sheet_name: str,
    nrows: Optional[int] = None,
) -> pd.DataFrame:
    """
    Read a worksheet into a DataFrame.
    - No formula execution (data_only handled by openpyxl).
    - Strips whitespace from string columns.
    - Does NOT modify or delete original data.
    """
    try:
        engine = _pick_engine(path)
        read_kwargs: dict = {
            "sheet_name": sheet_name,
            "engine": engine,
        }
        if nrows is not None:
            read_kwargs["nrows"] = nrows

        df = pd.read_excel(path, **read_kwargs)
    except Exception as exc:
        raise ValueError(f"Failed to read sheet '{sheet_name}': {exc}") from exc

    if df.empty:
        raise ValueError(f"Sheet '{sheet_name}' contains no data.")

    # Strip whitespace from object columns only
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].str.strip()

    logger.info(
        "Read sheet '%s' from '%s': %d rows × %d cols",
        sheet_name,
        path.name,
        len(df),
        len(df.columns),
    )
    return df


def preview_dataframe(df: pd.DataFrame, nrows: int = 10) -> pd.DataFrame:
    """Return the first nrows rows for display (read-only view)."""
    return df.head(nrows).copy()
