# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-07-28

### Added

- MCP SDK 2.x support: the server now imports `MCPServer` on SDK 2.x and falls
  back to `FastMCP` on SDK 1.x, and the dependency pin widens to
  `mcp>=1.2.0,<3`. Verified against both SDK lines.
- `examples/sample.csv`: a small sales export with deliberate quality issues
  (missing regions, a duplicate row, a constant column, whitespace padding) to
  try the tools on.

## [0.1.4] - 2026-07-28

### Fixed

- Pin `mcp>=1.2.0,<2`. MCP Python SDK 2.0 (released 2026-07-27) removes the
  `mcp.server.fastmcp` import path (`FastMCP` became
  `mcp.server.mcpserver.MCPServer`), so fresh installs resolving `mcp==2.0.0`
  crashed on startup with `ModuleNotFoundError`. Migration to SDK v2 is
  planned separately.

## [0.1.3] - 2026-07-27

### Added

- Python 3.13 in the CI test matrix and package classifiers.

### Changed

- CI now runs `ruff check` as a lint job; ruff configuration pinned in
  `pyproject.toml`.
- Text-column detection uses the pandas dtype API (`is_object_dtype`) instead
  of a raw `dtype == object` comparison.

## [0.1.2] - 2026-07-21

### Added

- Published to the official [MCP Registry](https://registry.modelcontextprotocol.io)
  as `io.github.haiiibin/data-profiler-mcp` (`server.json`).
- Glama listing metadata (`glama.json`) and score badge.
- `Dockerfile` (stdio) for containerized runs.

## [0.1.1] - 2026-07-11

### Fixed

- The documented `max_rows` cap is now enforced at the MCP layer, so oversized
  requests are rejected instead of silently truncated differently per loader.

### Added

- Quality detection flags dates stored as text.
- GitHub Actions CI (test matrix py3.10 to py3.12).

## [0.1.0] - 2026-07-10

### Added

- Initial release: `profile_dataset`, `preview_data`, `column_stats`,
  `detect_quality_issues`, `suggest_dtypes`, `compare_datasets` over CSV, TSV,
  Parquet, Excel, JSON and JSON Lines.
- Terminal demo GIF and PyPI packaging.

[0.2.0]: https://github.com/haiiibin/data-profiler-mcp/compare/v0.1.4...v0.2.0
[0.1.4]: https://github.com/haiiibin/data-profiler-mcp/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/haiiibin/data-profiler-mcp/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/haiiibin/data-profiler-mcp/releases/tag/v0.1.2
[0.1.1]: https://github.com/haiiibin/data-profiler-mcp/releases/tag/v0.1.2
[0.1.0]: https://github.com/haiiibin/data-profiler-mcp/releases/tag/v0.1.2
