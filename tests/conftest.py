"""Shared fixtures: a synthetic dataset written out in several formats.

The dataset is deliberately messy so the profiling and quality-detection code
has something to find: missing values, a duplicate row, a constant column,
numbers stored as text, a mixed-type column, whitespace padding, an outlier,
and an all-empty column.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def build_dataset(n: int = 200) -> pd.DataFrame:
    idx = np.arange(n)
    df = pd.DataFrame(
        {
            "id": idx.astype("int64"),
            "uid": [f"U{i:04d}" for i in idx],  # unique object -> likely identifier
            "category": np.where(
                idx % 3 == 0, "A", np.where(idx % 3 == 1, "B", "C")
            ).astype(object),  # low cardinality -> category
            "price": (idx % 50).astype("float64"),
            "flag": (idx % 2 == 0),
            "const": ["X"] * n,  # constant column
            "numeric_text": [str(int(v)) for v in (idx % 100)],  # numbers as text
            "mixed": [str(int(idx[i])) if i % 2 == 0 else "xx" for i in range(n)],
            "padded": [f" val{i % 5} " for i in idx],  # leading/trailing spaces
            "ts": pd.date_range("2024-01-01", periods=n, freq="h"),
            "notes": [None if i % 10 < 3 else f"note{i}" for i in idx],  # ~30% missing
            "sparse": [None if i % 10 < 6 else float(i) for i in idx],  # ~60% missing
            "empty_col": [np.nan] * n,  # entirely missing
        }
    )
    df.loc[0, "price"] = 100_000.0  # outlier
    # Append an exact duplicate of the first row.
    return pd.concat([df, df.iloc[[0]]], ignore_index=True)


@pytest.fixture(scope="session")
def sample_df() -> pd.DataFrame:
    return build_dataset()


@pytest.fixture(scope="session")
def parquet_path(tmp_path_factory, sample_df) -> str:
    """Parquet preserves dtypes exactly, so detailed assertions use this file."""
    p = tmp_path_factory.mktemp("data") / "sample.parquet"
    sample_df.to_parquet(p)
    return str(p)


@pytest.fixture(scope="session")
def csv_path(tmp_path_factory, sample_df) -> str:
    p = tmp_path_factory.mktemp("data") / "sample.csv"
    sample_df.to_csv(p, index=False)
    return str(p)


@pytest.fixture(scope="session")
def tsv_path(tmp_path_factory, sample_df) -> str:
    p = tmp_path_factory.mktemp("data") / "sample.tsv"
    sample_df.to_csv(p, sep="\t", index=False)
    return str(p)


@pytest.fixture(scope="session")
def excel_path(tmp_path_factory, sample_df) -> str:
    p = tmp_path_factory.mktemp("data") / "sample.xlsx"
    sample_df.to_excel(p, index=False)
    return str(p)


@pytest.fixture(scope="session")
def json_path(tmp_path_factory, sample_df) -> str:
    p = tmp_path_factory.mktemp("data") / "sample.json"
    sample_df.to_json(p, orient="records", date_format="iso")
    return str(p)


@pytest.fixture(scope="session")
def dataset_v2_path(tmp_path_factory, sample_df) -> str:
    """A modified version of the dataset for compare_datasets."""
    df_b = sample_df.drop(columns=["category"]).copy()
    df_b["new_col"] = 1
    p = tmp_path_factory.mktemp("data") / "sample_v2.parquet"
    df_b.to_parquet(p)
    return str(p)
