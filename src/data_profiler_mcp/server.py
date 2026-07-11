"""MCP server exposing the data-profiling tools.

The tool docstrings below are what the LLM sees, so they are written as guidance
for an agent: what the tool does, when to reach for it, and what it returns.
They are plain triple-quoted strings (never f-strings) so ``__doc__`` is set and
FastMCP can read them as tool descriptions.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from data_profiler_mcp import profiling
from data_profiler_mcp.loaders import DEFAULT_MAX_ROWS

mcp = FastMCP("data-profiler")


def _effective_max_rows(max_rows: int | None) -> int | None:
    """Translate the tool-level ``max_rows`` argument for the engine.

    The tools default to ``None``, which must mean "use the documented default
    cap", not "unlimited" (the engine treats ``None`` as unlimited). Passing
    ``0`` or a negative number explicitly removes the cap.
    """
    if max_rows is None:
        return DEFAULT_MAX_ROWS
    if max_rows <= 0:
        return None
    return max_rows


@mcp.tool()
def profile_dataset(path: str, max_rows: int | None = None) -> dict:
    """Profile a tabular data file in one call: the fastest way to understand a dataset.

    Reads the file at ``path`` (CSV, TSV, Parquet, Excel or JSON/JSONL, detected
    from the extension) and returns a structured overview:

    - file metadata (format, size),
    - shape (row and column counts, and whether the profile was sampled),
    - total memory footprint,
    - a missing-value summary and a duplicate-row count,
    - a per-column summary (dtype, inferred type, null %, unique %, sample
      values, and basic stats for numeric/datetime columns), and
    - a list of plain-language data-quality flags.

    Use this first whenever a user points you at a data file and wants to know
    what is in it. ``max_rows`` caps how many rows are read (default: up to one
    million); the result flags when the file was larger and the stats are a
    head sample. Pass 0 to remove the cap entirely.
    """
    return profiling.profile_dataset(path, max_rows=_effective_max_rows(max_rows))


@mcp.tool()
def preview_data(path: str, n: int = 10, mode: str = "head") -> dict:
    """Peek at actual rows of a data file.

    Returns ``n`` rows (capped at 100) as records. ``mode`` selects which rows:
    ``head`` (default), ``tail``, or ``sample`` (random). Use this to see real
    example values rather than just statistics, for example to check formatting,
    encodings, or how a specific column looks in practice.
    """
    return profiling.preview_data(path, n=n, mode=mode)


@mcp.tool()
def column_stats(path: str, column: str, max_rows: int | None = None) -> dict:
    """Deep statistical dive on a single column.

    For numeric columns: min/max, mean, std, a full set of percentiles
    (p1/p5/q1/median/q3/p95/p99), skewness, kurtosis, zero and negative counts,
    an IQR-based outlier count with bounds, and a 10-bin histogram. For datetime
    columns: the min and max timestamp. For text/categorical columns: the top
    values with counts and percentages, plus string-length statistics.

    Reach for this after ``profile_dataset`` when one column needs closer
    inspection. Raises an error listing the available columns if ``column`` is
    not found.
    """
    return profiling.column_stats(path, column, max_rows=_effective_max_rows(max_rows))


@mcp.tool()
def detect_quality_issues(path: str, max_rows: int | None = None) -> dict:
    """Run a focused data-quality audit and return issues grouped by severity.

    Detects duplicate rows, all-missing and high-missing columns, constant
    columns, likely identifier columns, numbers stored as text, dates stored as
    text, columns mixing numeric and text values, leading/trailing whitespace,
    and empty (whitespace-only) strings. Each issue carries a column (or ``null`` for
    table-level), an issue code, a severity (``high``/``warning``/``info``), and
    a plain-language explanation.

    Use this when the user cares specifically about cleanliness, is preparing
    data for modeling, or asks "is anything wrong with this data?".
    """
    return profiling.detect_quality_issues(path, max_rows=_effective_max_rows(max_rows))


@mcp.tool()
def suggest_dtypes(path: str, max_rows: int | None = None) -> dict:
    """Recommend more memory-efficient or more-correct column dtypes.

    For each column, proposes a better dtype when one exists: text that is fully
    numeric to a numeric type, low-cardinality text to ``category``, and
    oversized integer/float columns downcast to smaller types. Reports per-column
    and total estimated memory savings.

    Use this to help a user shrink a DataFrame's memory footprint or fix columns
    that were loaded with the wrong type.
    """
    return profiling.suggest_dtypes(path, max_rows=_effective_max_rows(max_rows))


@mcp.tool()
def compare_datasets(path_a: str, path_b: str, max_rows: int | None = None) -> dict:
    """Diff two tabular files: what changed between version A and version B.

    Reports the row-count delta, columns added or removed in B, dtype changes on
    shared columns, and per-column null-rate (and, for numeric columns, mean)
    for both files side by side.

    Use this to compare two snapshots of the same dataset, validate a data
    pipeline's output against a baseline, or check what a transformation changed.
    """
    return profiling.compare_datasets(path_a, path_b, max_rows=_effective_max_rows(max_rows))


def main() -> None:
    """Console-script entry point: run the server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
