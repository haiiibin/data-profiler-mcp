"""Tests for the correlation_matrix tool."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from data_profiler_mcp import profiling


@pytest.fixture()
def corr_csv(tmp_path):
    rng = np.random.default_rng(42)
    x = rng.normal(size=200)
    df = pd.DataFrame(
        {
            "x": x,
            "double_x": 2 * x,
            "noise": rng.normal(size=200),
            "constant": 1,
            "label": ["a", "b"] * 100,
        }
    )
    path = tmp_path / "corr.csv"
    df.to_csv(path, index=False)
    return str(path)


def test_constant_and_text_columns_excluded(corr_csv):
    result = profiling.correlation_matrix(corr_csv)
    assert result["constant_columns_excluded"] == ["constant"]
    assert set(result["columns_used"]) == {"x", "double_x", "noise"}


def test_perfectly_correlated_pair_ranks_first_and_flags_high(corr_csv):
    result = profiling.correlation_matrix(corr_csv)
    top = result["pairs"][0]
    assert {top["column_a"], top["column_b"]} == {"x", "double_x"}
    assert top["r"] == pytest.approx(1.0)
    assert any(
        {p["column_a"], p["column_b"]} == {"x", "double_x"}
        for p in result["high_correlation_pairs"]
    )


def test_matrix_present_and_symmetric_for_small_files(corr_csv):
    result = profiling.correlation_matrix(corr_csv)
    matrix = result["matrix"]
    assert matrix is not None
    assert matrix["x"]["double_x"] == matrix["double_x"]["x"]
    assert matrix["x"]["x"] == pytest.approx(1.0)


def test_target_column_mode_ranks_others_and_omits_matrix(corr_csv):
    result = profiling.correlation_matrix(corr_csv, column="x")
    assert result["matrix"] is None
    assert all(p["column_a"] == "x" for p in result["pairs"])
    assert "x" not in {p["column_b"] for p in result["pairs"]}
    assert result["pairs"][0]["column_b"] == "double_x"


def test_spearman_catches_monotonic_nonlinear_relationship(tmp_path):
    x = np.arange(1, 101, dtype=float)
    df = pd.DataFrame({"x": x, "cubed": x**3})
    path = tmp_path / "mono.csv"
    df.to_csv(path, index=False)
    result = profiling.correlation_matrix(str(path), method="spearman")
    assert result["pairs"][0]["r"] == pytest.approx(1.0)


def test_fewer_than_two_numeric_columns_returns_note(tmp_path):
    df = pd.DataFrame({"only": [1.0, 2.0, 3.0], "text": ["a", "b", "c"]})
    path = tmp_path / "single.csv"
    df.to_csv(path, index=False)
    result = profiling.correlation_matrix(str(path))
    assert result["pairs"] == []
    assert "note" in result


def test_invalid_method_and_bad_column_raise(corr_csv):
    with pytest.raises(ValueError, match="method"):
        profiling.correlation_matrix(corr_csv, method="cosine")
    with pytest.raises(ValueError, match="not found"):
        profiling.correlation_matrix(corr_csv, column="missing")
    with pytest.raises(ValueError, match="not usable"):
        profiling.correlation_matrix(corr_csv, column="label")
