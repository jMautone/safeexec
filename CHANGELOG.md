# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-11-14

First public release.

### Added

- `POST /v1/executions`: run Python or JavaScript in a single-use container and get
  back stdout, stderr, exit code, duration and `timed_out` / `oom_killed` /
  `*_truncated` flags.
- Hardened executor: non-root user, no network, read-only root filesystem with a
  32 MB tmpfs, no swap, CPU and pids caps, all capabilities dropped,
  `no-new-privileges`, wall-clock kill, forced removal. Optional gVisor runtime.
- Limits policy with safe defaults, configurable hard maximums and actionable 422s.
- Idempotency by `client_request_id`, backed by a unique constraint in Postgres.
- Capacity limiting (429 + `Retry-After`) and graceful 503 when Docker is down.
- JSON logs with request ids, `/healthz`, Prometheus `/metrics`.
- Example LLM correction loop (`examples/llm_loop.py`) with an offline mode.
- CI: lint, format, mypy strict, unit/API tests, migrations, contract tests against
  real containers.

### Fixed

- Container output is read as a stream and cut at `max_output_bytes`, so a program
  that floods stdout can no longer grow the API process's memory.

[0.1.0]: https://github.com/jMautone/safeexec/releases/tag/v0.1.0
