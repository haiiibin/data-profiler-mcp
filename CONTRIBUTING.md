# Contributing

Thanks for your interest in improving data-profiler-mcp. Bug reports, feature
ideas, and pull requests are all welcome.

## Development setup

```bash
git clone https://github.com/haiiibin/data-profiler-mcp
cd data-profiler-mcp
python -m venv .venv && source .venv/bin/activate   # .venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

## Running checks

```bash
pytest -q          # test suite
ruff check .       # lint (config lives in pyproject.toml)
```

Both must pass before a PR can merge. CI also runs the suite on Python 3.10
through 3.13.

## MCP SDK compatibility

The server supports both MCP SDK 1.x (`mcp.server.fastmcp.FastMCP`) and 2.x
(`mcp.server.mcpserver.MCPServer`) through the import shim in
`src/data_profiler_mcp/server.py`. If you touch server wiring, run the tests
against both majors; CI's `test-mcp1` job pins `mcp<2` to guard the fallback
path, and the regular matrix exercises the current SDK.

```bash
pip install "mcp>=1.2.0,<2" && pytest -q   # 1.x path
pip install --upgrade "mcp<3" && pytest -q # 2.x path
```

## Pull request guidelines

- Keep changes focused; one concern per PR.
- Add or update tests for any behavior change.
- Update `CHANGELOG.md` under `[Unreleased]`.
- New tools need a docstring (it becomes the tool description shown to LLMs)
  and a row in the README tool table.

## Reporting bugs

Please use the bug-report issue template. A minimal sample file that
reproduces the problem (or a snippet that generates one) makes fixes much
faster.
