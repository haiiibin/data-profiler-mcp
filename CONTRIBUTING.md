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

The server targets MCP Python SDK 2.x (`mcp>=2,<3`) through
`mcp.server.MCPServer`. SDK 1.x is feature-frozen upstream (it stops at the
2025-11-25 protocol revision and only receives critical fixes), so it is not
supported and no import shim should be added for it; 0.3.0 was the last
release that ran on 1.x.

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
