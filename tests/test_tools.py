"""Tests that the MCP server registers the tools with usable descriptions."""

from __future__ import annotations

import json

from data_profiler_mcp import server

EXPECTED_TOOLS = {
    "profile_dataset",
    "preview_data",
    "column_stats",
    "detect_quality_issues",
    "suggest_dtypes",
    "compare_datasets",
}


def _registered_tools():
    return server.mcp._tool_manager.list_tools()


def test_all_tools_registered():
    names = {t.name for t in _registered_tools()}
    assert EXPECTED_TOOLS <= names


def test_every_tool_has_a_nonempty_description():
    for tool in _registered_tools():
        assert tool.description and tool.description.strip(), (
            f"tool {tool.name} has an empty description"
        )


def test_tool_wrappers_return_serializable(parquet_path):
    # The decorated functions remain directly callable.
    for fn, args in [
        (server.profile_dataset, (parquet_path,)),
        (server.preview_data, (parquet_path,)),
        (server.column_stats, (parquet_path, "price")),
        (server.detect_quality_issues, (parquet_path,)),
        (server.suggest_dtypes, (parquet_path,)),
    ]:
        result = fn(*args)
        assert isinstance(result, dict)
        json.dumps(result)
