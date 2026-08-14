# Security Policy

## Supported versions

Only the latest release on PyPI receives fixes.

## Reporting a vulnerability

Please do not open a public issue for security problems. Report them privately
via [GitHub private vulnerability reporting](https://github.com/haiiibin/data-profiler-mcp/security/advisories/new)
or email haibiny123@gmail.com. You can expect an initial response within a few
days.

## Scope notes

This server reads local tabular files that the host explicitly passes to it and
returns derived statistics. It performs no network calls at runtime. Reports
about path handling (e.g. reading files outside what the host intended) are
particularly welcome.
