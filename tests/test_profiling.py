"""Tests for the profiling engine against the faithful parquet fixture."""

from __future__ import annotations

import json

import pytest

from data_profiler_mcp import profiling


def _col(profile, name):
    return next(c for c in profile["columns"] if c["name"] == name)


def test_profile_dataset_shape_and_serializable(parquet_path):
    profile = profiling.profile_dataset(parquet_path)
    # Must be JSON-serializable end to end.
    json.dumps(profile)

    assert profile["shape"]["rows"] == 201
    assert profile["shape"]["columns"] == 13
    assert profile["duplicate_rows"]["count"] == 1
    assert profile["missing_summary"]["columns_with_missing"] >= 3
    assert isinstance(profile["quality_flags"], list)
    assert len(profile["quality_flags"]) > 0


def test_profile_column_details(parquet_path):
    profile = profiling.profile_dataset(parquet_path)

    assert _col(profile, "const")["is_constant"] is True
    assert _col(profile, "empty_col")["inferred_type"] == "empty"
    assert _col(profile, "category")["inferred_type"] == "categorical"
    assert _col(profile, "uid")["inferred_type"] == "text"

    price = _col(profile, "price")
    assert price["inferred_type"] == "float"
    assert price["stats"]["max"] == 100000.0


def test_detect_quality_issues(parquet_path):
    report = profiling.detect_quality_issues(parquet_path)
    codes = {i["issue"] for i in report["issues"]}

    for expected in {
        "duplicate_rows",
        "constant_column",
        "all_missing",
        "high_missing",
        "numeric_stored_as_text",
        "mixed_numeric_and_text",
        "whitespace_padding",
    }:
        assert expected in codes, f"expected issue {expected!r} not found in {codes}"

    assert report["severity_counts"]["high"] >= 1
    # Issues are sorted high severity first.
    severities = [i["severity"] for i in report["issues"]]
    assert severities == sorted(severities, key={"high": 0, "warning": 1, "info": 2}.get)


def test_suggest_dtypes(parquet_path):
    result = profiling.suggest_dtypes(parquet_path)
    by_col = {s["column"]: s for s in result["suggestions"]}

    assert "numeric_text" in by_col
    assert "category" in by_col
    assert by_col["category"]["suggested_dtype"] == "category"
    assert "id" in by_col  # int64 downcast to a smaller int
    assert result["projected_memory_bytes"] <= result["current_memory_bytes"]


def test_column_stats_numeric(parquet_path):
    stats = profiling.column_stats(parquet_path, "price")
    assert stats["inferred_type"] == "float"
    assert stats["numeric"]["iqr_outliers"]["count"] >= 1
    assert len(stats["histogram"]["counts"]) > 0
    json.dumps(stats)


def test_column_stats_categorical(parquet_path):
    stats = profiling.column_stats(parquet_path, "category")
    assert stats["categorical"]["top_values"]
    assert stats["categorical"]["top_values"][0]["count"] > 0


def test_column_stats_datetime(parquet_path):
    stats = profiling.column_stats(parquet_path, "ts")
    assert stats["inferred_type"] == "datetime"
    assert stats["datetime"]["min"] is not None
    assert stats["datetime"]["max"] is not None


def test_column_stats_unknown_column(parquet_path):
    with pytest.raises(KeyError):
        profiling.column_stats(parquet_path, "no_such_column")


def test_preview_data_modes(parquet_path):
    head = profiling.preview_data(parquet_path, n=10, mode="head")
    assert head["mode"] == "head"
    assert head["returned_rows"] == 10
    assert len(head["columns"]) == 13
    assert isinstance(head["rows"], list) and len(head["rows"]) == 10
    json.dumps(head)

    tail = profiling.preview_data(parquet_path, n=5, mode="tail")
    assert tail["mode"] == "tail"
    assert tail["returned_rows"] == 5

    sample = profiling.preview_data(parquet_path, n=7, mode="sample")
    assert sample["mode"] == "sample"
    assert sample["returned_rows"] == 7


def test_preview_data_caps_n(parquet_path):
    out = profiling.preview_data(parquet_path, n=9999, mode="head")
    assert out["returned_rows"] <= 100


def test_clean_dataset_no_false_positives(tmp_path):
    import numpy as np
    import pandas as pd

    clean = pd.DataFrame(
        {
            "a": np.arange(100, dtype="int64"),
            "b": np.linspace(0.0, 1.0, 100),
            "c": ["x", "y"] * 50,
        }
    )
    p = tmp_path / "clean.parquet"
    clean.to_parquet(p)
    report = profiling.detect_quality_issues(str(p))
    assert report["issue_count"] == 0
    assert profiling.profile_dataset(str(p))["quality_flags"] == []


def test_empty_dataframe_does_not_crash(tmp_path):
    import pandas as pd

    empty = pd.DataFrame(
        {"a": pd.Series([], dtype="float64"), "b": pd.Series([], dtype="object")}
    )
    p = tmp_path / "empty.parquet"
    empty.to_parquet(p)

    profile = profiling.profile_dataset(str(p))
    assert profile["shape"]["rows"] == 0
    json.dumps(profile)

    # Other tools should also survive an empty frame.
    json.dumps(profiling.detect_quality_issues(str(p)))
    json.dumps(profiling.suggest_dtypes(str(p)))
    json.dumps(profiling.preview_data(str(p)))


def test_compare_datasets(parquet_path, dataset_v2_path):
    diff = profiling.compare_datasets(parquet_path, dataset_v2_path)
    assert "new_col" in diff["columns"]["added_in_b"]
    assert "category" in diff["columns"]["removed_in_b"]
    assert diff["row_count_delta"] == 0
    json.dumps(diff)
