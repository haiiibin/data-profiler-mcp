"""Core profiling logic.

Every public function returns a plain, JSON-serializable ``dict`` (or ``list``)
so the output can be handed straight back to an LLM. NumPy scalars, NaN/inf and
timestamps are normalized by :func:`_clean` before returning.
"""

from __future__ import annotations

import math
import os
import warnings

import numpy as np
import pandas as pd

from data_profiler_mcp.loaders import DEFAULT_MAX_ROWS, load_dataframe, resolve_path

# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _clean(obj):
    """Recursively convert an object into JSON-safe primitives."""
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [_clean(v) for v in obj.tolist()]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        f = float(obj)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, (pd.Timestamp,)):
        return None if pd.isna(obj) else obj.isoformat()
    if obj is pd.NaT or obj is None:
        return None
    # Scalar pandas NA
    try:
        if pd.isna(obj):
            return None
    except (TypeError, ValueError):
        pass
    return obj


def _human_bytes(n: int | float) -> str:
    """Format a byte count as a human-readable string."""
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024.0:
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} {unit}"
        n /= 1024.0
    return f"{n:.1f} PB"


def _round(x, ndigits: int = 4):
    """Round a numeric value, passing NaN/None through untouched."""
    if x is None:
        return None
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return x
    if math.isnan(xf) or math.isinf(xf):
        return None
    return round(xf, ndigits)


# ---------------------------------------------------------------------------
# Type inference
# ---------------------------------------------------------------------------


def _is_text_column(s: pd.Series) -> bool:
    """True for object or string-dtype columns.

    pandas 3+/4 loads text as a dedicated string dtype rather than ``object``,
    so gating on ``dtype == object`` alone silently skips real text columns.
    """
    dtype = s.dtype
    if dtype == object:
        return True
    if isinstance(dtype, pd.StringDtype):
        return True
    return (
        pd.api.types.is_string_dtype(dtype)
        and not pd.api.types.is_numeric_dtype(dtype)
        and not pd.api.types.is_bool_dtype(dtype)
        and not pd.api.types.is_datetime64_any_dtype(dtype)
    )


def _inferred_type(s: pd.Series) -> str:
    """Classify a column into a coarse semantic type family."""
    non_null = s.dropna()
    if len(non_null) == 0:
        return "empty"
    if pd.api.types.is_bool_dtype(s):
        return "boolean"
    if pd.api.types.is_datetime64_any_dtype(s):
        return "datetime"
    if pd.api.types.is_integer_dtype(s):
        return "integer"
    if pd.api.types.is_float_dtype(s):
        return "float"
    # object / string columns
    nunique = non_null.nunique()
    ratio = nunique / len(non_null)
    if nunique <= 50 and ratio < 0.5:
        return "categorical"
    return "text"


def _sample_values(s: pd.Series, n: int = 5) -> list:
    """Return up to ``n`` distinct non-null example values."""
    vals = s.dropna().unique()[:n]
    return [_clean(v) for v in vals]


# ---------------------------------------------------------------------------
# File metadata
# ---------------------------------------------------------------------------


def _file_meta(path, fmt: str) -> dict:
    p = resolve_path(path)
    size = os.path.getsize(p)
    return {
        "path": str(p),
        "name": p.name,
        "format": fmt,
        "size_bytes": size,
        "size_human": _human_bytes(size),
    }


def _shape_block(df: pd.DataFrame, truncated: bool) -> dict:
    block = {
        "rows": int(len(df)),
        "columns": int(df.shape[1]),
        "sampled": bool(truncated),
    }
    if truncated:
        block["note"] = (
            f"File is larger than the row cap; statistics are based on the first "
            f"{len(df):,} rows. Pass a larger 'max_rows' to profile more."
        )
    return block


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def profile_dataset(path, max_rows: int | None = DEFAULT_MAX_ROWS) -> dict:
    """Full profile: shape, per-column summaries, missingness, duplicates, flags."""
    df, fmt, truncated = load_dataframe(path, max_rows=max_rows)

    columns = [_column_summary(df[col]) for col in df.columns]

    total_cells = int(df.size)
    missing_cells = int(df.isna().sum().sum())
    cols_with_missing = int((df.isna().sum() > 0).sum())

    dup_count = int(df.duplicated().sum())

    result = {
        "file": _file_meta(path, fmt),
        "shape": _shape_block(df, truncated),
        "memory_usage_bytes": int(df.memory_usage(deep=True).sum()),
        "memory_usage_human": _human_bytes(int(df.memory_usage(deep=True).sum())),
        "missing_summary": {
            "total_missing_cells": missing_cells,
            "pct_missing": _round(100 * missing_cells / total_cells if total_cells else 0, 2),
            "columns_with_missing": cols_with_missing,
        },
        "duplicate_rows": {
            "count": dup_count,
            "pct": _round(100 * dup_count / len(df) if len(df) else 0, 2),
        },
        "columns": columns,
        "quality_flags": _quality_flags(df),
    }
    return _clean(result)


def _column_summary(s: pd.Series) -> dict:
    n = len(s)
    non_null = int(s.notna().sum())
    null = n - non_null
    nunique = int(s.nunique(dropna=True))
    inferred = _inferred_type(s)

    summary = {
        "name": str(s.name),
        "dtype": str(s.dtype),
        "inferred_type": inferred,
        "non_null": non_null,
        "null": null,
        "null_pct": _round(100 * null / n if n else 0, 2),
        "unique": nunique,
        "unique_pct": _round(100 * nunique / non_null if non_null else 0, 2),
        "is_constant": bool(nunique <= 1),
        "sample_values": _sample_values(s),
    }

    if inferred in ("integer", "float"):
        clean = s.dropna()
        summary["stats"] = {
            "min": _round(clean.min()),
            "max": _round(clean.max()),
            "mean": _round(clean.mean()),
            "std": _round(clean.std()),
            "median": _round(clean.median()),
        }
    elif inferred == "datetime":
        clean = s.dropna()
        summary["stats"] = {
            "min": _clean(clean.min()) if len(clean) else None,
            "max": _clean(clean.max()) if len(clean) else None,
        }
    elif inferred in ("categorical", "text", "boolean"):
        vc = s.dropna().value_counts()
        if len(vc):
            summary["top"] = _clean(vc.index[0])
            summary["top_freq"] = int(vc.iloc[0])

    return summary


def column_stats(path, column: str, max_rows: int | None = DEFAULT_MAX_ROWS) -> dict:
    """Deep statistical dive on a single column."""
    df, fmt, truncated = load_dataframe(path, max_rows=max_rows)
    if column not in df.columns:
        raise KeyError(
            f"Column {column!r} not found. Available columns: {list(df.columns)}"
        )

    s = df[column]
    n = len(s)
    non_null = int(s.notna().sum())
    inferred = _inferred_type(s)

    out = {
        "file": _file_meta(path, fmt),
        "column": str(column),
        "dtype": str(s.dtype),
        "inferred_type": inferred,
        "count": n,
        "non_null": non_null,
        "null": n - non_null,
        "null_pct": _round(100 * (n - non_null) / n if n else 0, 2),
        "unique": int(s.nunique(dropna=True)),
        "unique_pct": _round(100 * s.nunique(dropna=True) / non_null if non_null else 0, 2),
        "sampled": bool(truncated),
    }

    if inferred in ("integer", "float"):
        out["numeric"] = _numeric_detail(s.dropna())
        out["histogram"] = _histogram(s.dropna())
    elif inferred == "datetime":
        clean = s.dropna()
        out["datetime"] = {
            "min": _clean(clean.min()) if len(clean) else None,
            "max": _clean(clean.max()) if len(clean) else None,
        }
    else:
        out["categorical"] = _categorical_detail(s)

    return _clean(out)


def _numeric_detail(clean: pd.Series) -> dict:
    if len(clean) == 0:
        return {}
    q1 = clean.quantile(0.25)
    q3 = clean.quantile(0.75)
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    outliers = int(((clean < lower) | (clean > upper)).sum())
    return {
        "min": _round(clean.min()),
        "p1": _round(clean.quantile(0.01)),
        "p5": _round(clean.quantile(0.05)),
        "q1": _round(q1),
        "median": _round(clean.median()),
        "q3": _round(q3),
        "p95": _round(clean.quantile(0.95)),
        "p99": _round(clean.quantile(0.99)),
        "max": _round(clean.max()),
        "mean": _round(clean.mean()),
        "std": _round(clean.std()),
        "skew": _round(clean.skew()),
        "kurtosis": _round(clean.kurtosis()),
        "zeros": int((clean == 0).sum()),
        "negatives": int((clean < 0).sum()),
        "iqr_outliers": {
            "count": outliers,
            "pct": _round(100 * outliers / len(clean), 2),
            "lower_bound": _round(lower),
            "upper_bound": _round(upper),
        },
    }


def _histogram(clean: pd.Series, bins: int = 10) -> dict:
    if len(clean) == 0 or clean.nunique() <= 1:
        return {"bin_edges": [], "counts": []}
    counts, edges = np.histogram(clean.to_numpy(), bins=bins)
    return {
        "bin_edges": [_round(e) for e in edges.tolist()],
        "counts": [int(c) for c in counts.tolist()],
    }


def _categorical_detail(s: pd.Series, top_n: int = 10) -> dict:
    non_null = s.dropna()
    total = len(non_null)
    vc = non_null.value_counts().head(top_n)
    top_values = [
        {
            "value": _clean(idx),
            "count": int(cnt),
            "pct": _round(100 * cnt / total if total else 0, 2),
        }
        for idx, cnt in vc.items()
    ]
    detail = {"top_values": top_values}

    # String-length stats for object/text columns.
    if _is_text_column(s):
        lengths = non_null.astype(str).str.len()
        if len(lengths):
            detail["value_length"] = {
                "min": int(lengths.min()),
                "max": int(lengths.max()),
                "mean": _round(lengths.mean(), 2),
            }
    return detail


def detect_quality_issues(path, max_rows: int | None = DEFAULT_MAX_ROWS) -> dict:
    """Targeted data-quality report: issues grouped by severity."""
    df, fmt, truncated = load_dataframe(path, max_rows=max_rows)
    issues = _quality_issues(df)

    order = {"high": 0, "warning": 1, "info": 2}
    issues.sort(key=lambda i: order.get(i["severity"], 3))

    return _clean(
        {
            "file": _file_meta(path, fmt),
            "shape": _shape_block(df, truncated),
            "issue_count": len(issues),
            "severity_counts": {
                sev: sum(1 for i in issues if i["severity"] == sev)
                for sev in ("high", "warning", "info")
            },
            "issues": issues,
        }
    )


def _quality_issues(df: pd.DataFrame) -> list[dict]:
    issues: list[dict] = []
    n = len(df)

    # Table-level: duplicate rows.
    dup = int(df.duplicated().sum())
    if dup > 0:
        issues.append(
            {
                "column": None,
                "issue": "duplicate_rows",
                "severity": "warning" if dup / n < 0.1 else "high",
                "detail": f"{dup:,} duplicate rows ({100 * dup / n:.1f}% of the table).",
            }
        )

    for col in df.columns:
        s = df[col]
        non_null = int(s.notna().sum())
        null_pct = 100 * (n - non_null) / n if n else 0
        nunique = int(s.nunique(dropna=True))

        if non_null == 0:
            issues.append(
                {
                    "column": str(col),
                    "issue": "all_missing",
                    "severity": "high",
                    "detail": "Column is entirely empty (all values missing).",
                }
            )
            continue

        if null_pct >= 50:
            issues.append(
                {
                    "column": str(col),
                    "issue": "high_missing",
                    "severity": "high",
                    "detail": f"{null_pct:.1f}% of values are missing.",
                }
            )
        elif null_pct >= 20:
            issues.append(
                {
                    "column": str(col),
                    "issue": "missing_values",
                    "severity": "warning",
                    "detail": f"{null_pct:.1f}% of values are missing.",
                }
            )

        if nunique <= 1:
            issues.append(
                {
                    "column": str(col),
                    "issue": "constant_column",
                    "severity": "warning",
                    "detail": "Column holds a single constant value; it carries no information.",
                }
            )

        # Likely-identifier: text column where nearly every value is unique.
        if _is_text_column(s) and non_null > 100 and nunique / non_null > 0.95:
            issues.append(
                {
                    "column": str(col),
                    "issue": "likely_identifier",
                    "severity": "info",
                    "detail": f"{100 * nunique / non_null:.0f}% of values are unique; looks like an ID column.",
                }
            )

        if _is_text_column(s):
            _object_column_issues(s, col, issues)

    return issues


def _object_column_issues(s: pd.Series, col, issues: list[dict]) -> None:
    non_null = s.dropna()
    if len(non_null) == 0:
        return
    as_str = non_null.astype(str)

    # Numbers stored as text.
    coerced = pd.to_numeric(non_null, errors="coerce")
    numeric_ratio = coerced.notna().mean()
    if numeric_ratio == 1.0:
        issues.append(
            {
                "column": str(col),
                "issue": "numeric_stored_as_text",
                "severity": "warning",
                "detail": "Every value parses as a number but the column is stored as text.",
            }
        )
    elif 0.0 < numeric_ratio < 1.0 and numeric_ratio >= 0.5:
        issues.append(
            {
                "column": str(col),
                "issue": "mixed_numeric_and_text",
                "severity": "warning",
                "detail": f"{100 * numeric_ratio:.0f}% of values are numeric and the rest are text (mixed types).",
            }
        )

    # Dates stored as text. Only attempted when the column has no numeric
    # values at all, so digit strings like "20240101" are never misread as dates.
    if numeric_ratio == 0.0:
        sample = as_str.head(500)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
            except (ValueError, TypeError):
                parsed = None
        if parsed is not None and len(sample) > 0:
            rate = parsed.notna().mean()
            if rate >= 0.95:
                issues.append(
                    {
                        "column": str(col),
                        "issue": "datetime_stored_as_text",
                        "severity": "warning",
                        "detail": "Values parse as dates/timestamps but the column is stored as text.",
                    }
                )

    # Leading / trailing whitespace.
    stripped_diff = int((as_str != as_str.str.strip()).sum())
    if stripped_diff > 0:
        issues.append(
            {
                "column": str(col),
                "issue": "whitespace_padding",
                "severity": "info",
                "detail": f"{stripped_diff:,} values have leading or trailing whitespace.",
            }
        )

    # Empty / whitespace-only strings (distinct from NaN).
    blank = int((as_str.str.strip() == "").sum())
    if blank > 0:
        issues.append(
            {
                "column": str(col),
                "issue": "empty_strings",
                "severity": "info",
                "detail": f"{blank:,} values are empty or whitespace-only strings (not counted as NaN).",
            }
        )


def _quality_flags(df: pd.DataFrame) -> list[str]:
    """Short, human-readable one-line flags for the main profile."""
    flags = []
    for issue in _quality_issues(df):
        prefix = f"[{issue['severity']}]"
        where = f" {issue['column']}:" if issue["column"] else ""
        flags.append(f"{prefix}{where} {issue['detail']}")
    return flags


def suggest_dtypes(path, max_rows: int | None = DEFAULT_MAX_ROWS) -> dict:
    """Recommend memory-efficient / more-correct dtypes per column."""
    df, fmt, truncated = load_dataframe(path, max_rows=max_rows)

    suggestions = []
    current_total = int(df.memory_usage(deep=True).sum())
    projected_total = int(df.index.memory_usage(deep=True))

    for col in df.columns:
        s = df[col]
        cur_mem = int(s.memory_usage(deep=True))
        suggested_dtype, new_mem, reason = _suggest_column_dtype(s, cur_mem)
        projected_total += new_mem
        if suggested_dtype != str(s.dtype):
            suggestions.append(
                {
                    "column": str(col),
                    "current_dtype": str(s.dtype),
                    "suggested_dtype": suggested_dtype,
                    "reason": reason,
                    "current_bytes": cur_mem,
                    "estimated_bytes": new_mem,
                    "estimated_saving_bytes": cur_mem - new_mem,
                    "estimated_saving_pct": _round(
                        100 * (cur_mem - new_mem) / cur_mem if cur_mem else 0, 1
                    ),
                }
            )

    return _clean(
        {
            "file": _file_meta(path, fmt),
            "shape": _shape_block(df, truncated),
            "current_memory_bytes": current_total,
            "current_memory_human": _human_bytes(current_total),
            "projected_memory_bytes": projected_total,
            "projected_memory_human": _human_bytes(projected_total),
            "estimated_saving_pct": _round(
                100 * (current_total - projected_total) / current_total
                if current_total
                else 0,
                1,
            ),
            "suggestions": suggestions,
        }
    )


def _suggest_column_dtype(s: pd.Series, cur_mem: int) -> tuple[str, int, str | None]:
    """Return (suggested_dtype, estimated_bytes, reason) for one column."""
    dtype = str(s.dtype)
    non_null = s.dropna()

    if len(non_null) == 0:
        return dtype, cur_mem, None

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        if _is_text_column(s):
            # 1) Fully numeric text -> numeric.
            coerced = pd.to_numeric(non_null, errors="coerce")
            if coerced.notna().all():
                downcast = "integer" if (coerced % 1 == 0).all() else "float"
                converted = pd.to_numeric(s, errors="coerce").astype(
                    "float64" if downcast == "float" else "Int64"
                )
                new = pd.to_numeric(converted, downcast=downcast)
                return (
                    str(new.dtype),
                    int(new.memory_usage(deep=True)),
                    "stored as text but every value is numeric",
                )

            # 2) Low-cardinality -> category.
            ratio = non_null.nunique() / len(non_null)
            if ratio < 0.5:
                converted = s.astype("category")
                return (
                    "category",
                    int(converted.memory_usage(deep=True)),
                    f"low cardinality ({non_null.nunique()} distinct); category saves memory",
                )
            return dtype, cur_mem, None

        if pd.api.types.is_integer_dtype(s):
            new = pd.to_numeric(s, downcast="integer")
            if str(new.dtype) != dtype:
                return (
                    str(new.dtype),
                    int(new.memory_usage(deep=True)),
                    "values fit in a smaller integer type",
                )
            return dtype, cur_mem, None

        if pd.api.types.is_float_dtype(s):
            new = pd.to_numeric(s, downcast="float")
            if str(new.dtype) != dtype:
                return (
                    str(new.dtype),
                    int(new.memory_usage(deep=True)),
                    "values fit in float32 without loss of range",
                )
            return dtype, cur_mem, None

    return dtype, cur_mem, None


def preview_data(path, n: int = 10, mode: str = "head", max_rows: int | None = DEFAULT_MAX_ROWS) -> dict:
    """Return the first / last / a random sample of ``n`` rows as records."""
    n = max(1, min(int(n), 100))
    df, fmt, truncated = load_dataframe(path, max_rows=max_rows)

    if mode == "tail":
        view = df.tail(n)
    elif mode == "sample":
        view = df.sample(min(n, len(df))) if len(df) else df
    else:
        mode = "head"
        view = df.head(n)

    records = [{str(k): _clean(v) for k, v in row.items()} for row in view.to_dict(orient="records")]

    return _clean(
        {
            "file": _file_meta(path, fmt),
            "mode": mode,
            "returned_rows": len(records),
            "total_rows_scanned": int(len(df)),
            "columns": [str(c) for c in df.columns],
            "rows": records,
        }
    )


def compare_datasets(path_a, path_b, max_rows: int | None = DEFAULT_MAX_ROWS) -> dict:
    """Diff two datasets: columns, dtypes, row counts, and key statistics."""
    df_a, fmt_a, trunc_a = load_dataframe(path_a, max_rows=max_rows)
    df_b, fmt_b, trunc_b = load_dataframe(path_b, max_rows=max_rows)

    cols_a = list(df_a.columns)
    cols_b = list(df_b.columns)
    set_a, set_b = set(cols_a), set(cols_b)
    common = [c for c in cols_a if c in set_b]

    dtype_changes = []
    stat_changes = []
    for col in common:
        da, db = str(df_a[col].dtype), str(df_b[col].dtype)
        if da != db:
            dtype_changes.append({"column": str(col), "from": da, "to": db})

        null_a = _round(100 * df_a[col].isna().mean(), 2)
        null_b = _round(100 * df_b[col].isna().mean(), 2)
        entry = {
            "column": str(col),
            "null_pct_a": null_a,
            "null_pct_b": null_b,
        }
        if pd.api.types.is_numeric_dtype(df_a[col]) and pd.api.types.is_numeric_dtype(df_b[col]):
            entry["mean_a"] = _round(df_a[col].mean())
            entry["mean_b"] = _round(df_b[col].mean())
        stat_changes.append(entry)

    return _clean(
        {
            "a": {**_file_meta(path_a, fmt_a), "rows": int(len(df_a)), "sampled": bool(trunc_a)},
            "b": {**_file_meta(path_b, fmt_b), "rows": int(len(df_b)), "sampled": bool(trunc_b)},
            "row_count_delta": int(len(df_b) - len(df_a)),
            "columns": {
                "added_in_b": [str(c) for c in cols_b if c not in set_a],
                "removed_in_b": [str(c) for c in cols_a if c not in set_b],
                "common": [str(c) for c in common],
            },
            "dtype_changes": dtype_changes,
            "column_statistics": stat_changes,
        }
    )
