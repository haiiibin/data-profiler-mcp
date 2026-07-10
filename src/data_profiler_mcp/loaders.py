"""File loading and format detection for tabular data.

Supports CSV, TSV, Parquet, Excel, JSON and JSON Lines. The loader detects the
format from the file extension, reads it into a :class:`pandas.DataFrame`, and
can cap the number of rows so profiling stays responsive on very large files.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

# Default row cap applied when a caller does not pass ``max_rows``. Files with
# more rows than this are read up to the cap and flagged as truncated so the
# profile clearly says the statistics are based on a sample.
DEFAULT_MAX_ROWS = 1_000_000

_CSV_EXTS = {".csv", ".txt"}
_TSV_EXTS = {".tsv"}
_PARQUET_EXTS = {".parquet", ".pq"}
_EXCEL_EXTS = {".xlsx", ".xlsm", ".xls"}
_JSON_EXTS = {".json"}
_JSONL_EXTS = {".jsonl", ".ndjson"}

SUPPORTED_EXTENSIONS = (
    _CSV_EXTS
    | _TSV_EXTS
    | _PARQUET_EXTS
    | _EXCEL_EXTS
    | _JSON_EXTS
    | _JSONL_EXTS
)


def detect_format(path: str | os.PathLike) -> str:
    """Return a normalized format name for ``path`` based on its extension.

    Returns one of: ``csv``, ``tsv``, ``parquet``, ``excel``, ``json``,
    ``jsonl``. Raises :class:`ValueError` for unsupported extensions.
    """
    ext = Path(path).suffix.lower()
    if ext in _CSV_EXTS:
        return "csv"
    if ext in _TSV_EXTS:
        return "tsv"
    if ext in _PARQUET_EXTS:
        return "parquet"
    if ext in _EXCEL_EXTS:
        return "excel"
    if ext in _JSON_EXTS:
        return "json"
    if ext in _JSONL_EXTS:
        return "jsonl"
    supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
    raise ValueError(
        f"Unsupported file extension {ext!r}. Supported extensions: {supported}."
    )


def resolve_path(path: str | os.PathLike) -> Path:
    """Expand and validate ``path``, returning an absolute :class:`Path`.

    Raises :class:`FileNotFoundError` if the path does not exist and
    :class:`IsADirectoryError` if it points at a directory.
    """
    p = Path(os.path.expanduser(str(path))).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"No such file: {p}")
    if p.is_dir():
        raise IsADirectoryError(f"Path is a directory, not a data file: {p}")
    return p.resolve()


def load_dataframe(
    path: str | os.PathLike,
    max_rows: int | None = DEFAULT_MAX_ROWS,
    sheet: str | int | None = None,
) -> tuple[pd.DataFrame, str, bool]:
    """Load ``path`` into a DataFrame.

    Parameters
    ----------
    path:
        Path to the data file.
    max_rows:
        Cap on the number of rows read. ``None`` reads the whole file.
    sheet:
        Excel sheet name or index (ignored for non-Excel formats).

    Returns
    -------
    (dataframe, format_name, truncated)
        ``truncated`` is ``True`` when the file held more rows than ``max_rows``
        and the returned frame is therefore a head sample.
    """
    p = resolve_path(path)
    fmt = detect_format(p)

    # Read one extra row so we can tell whether the file was longer than the cap.
    read_cap = (max_rows + 1) if max_rows is not None else None

    if fmt == "csv":
        df = pd.read_csv(p, nrows=read_cap)
    elif fmt == "tsv":
        df = pd.read_csv(p, sep="\t", nrows=read_cap)
    elif fmt == "excel":
        df = pd.read_excel(p, sheet_name=(0 if sheet is None else sheet), nrows=read_cap)
    elif fmt == "parquet":
        df = pd.read_parquet(p)
    elif fmt == "json":
        df = pd.read_json(p)
    elif fmt == "jsonl":
        df = pd.read_json(p, lines=True)
    else:  # pragma: no cover - detect_format already guards this
        raise ValueError(f"Unsupported format: {fmt}")

    truncated = False
    if max_rows is not None and len(df) > max_rows:
        df = df.iloc[:max_rows].copy()
        truncated = True

    return df, fmt, truncated
