"""Tests for format detection and loading."""

from __future__ import annotations

import pytest

from data_profiler_mcp import loaders


@pytest.mark.parametrize(
    "name,expected",
    [
        ("a.csv", "csv"),
        ("a.txt", "csv"),
        ("a.tsv", "tsv"),
        ("a.parquet", "parquet"),
        ("a.pq", "parquet"),
        ("a.xlsx", "excel"),
        ("a.xls", "excel"),
        ("a.json", "json"),
        ("a.jsonl", "jsonl"),
        ("a.ndjson", "jsonl"),
        ("PATH/TO/DATA.CSV", "csv"),  # case-insensitive
    ],
)
def test_detect_format(name, expected):
    assert loaders.detect_format(name) == expected


def test_detect_format_unsupported():
    with pytest.raises(ValueError, match="Unsupported file extension"):
        loaders.detect_format("data.xml")


def test_resolve_path_missing():
    with pytest.raises(FileNotFoundError):
        loaders.resolve_path("does_not_exist_12345.csv")


def test_load_csv(csv_path):
    df, fmt, truncated = loaders.load_dataframe(csv_path)
    assert fmt == "csv"
    assert not truncated
    assert df.shape == (201, 13)


def test_load_parquet(parquet_path):
    df, fmt, truncated = loaders.load_dataframe(parquet_path)
    assert fmt == "parquet"
    assert df.shape == (201, 13)


def test_load_tsv(tsv_path):
    df, fmt, _ = loaders.load_dataframe(tsv_path)
    assert fmt == "tsv"
    assert df.shape == (201, 13)


def test_load_excel(excel_path):
    df, fmt, _ = loaders.load_dataframe(excel_path)
    assert fmt == "excel"
    assert df.shape == (201, 13)


def test_load_json(json_path):
    df, fmt, _ = loaders.load_dataframe(json_path)
    assert fmt == "json"
    assert df.shape == (201, 13)


def test_max_rows_truncation(csv_path):
    df, _, truncated = loaders.load_dataframe(csv_path, max_rows=50)
    assert len(df) == 50
    assert truncated is True


def test_no_truncation_when_cap_exceeds_rows(csv_path):
    df, _, truncated = loaders.load_dataframe(csv_path, max_rows=100_000)
    assert len(df) == 201
    assert truncated is False
