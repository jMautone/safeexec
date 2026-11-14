# AGENTS.md

Instructions for coding agents working on **SafeExec**.

## What this repo is

An HTTP API that runs AI-generated code in single-use, locked-down containers and
returns stdout/stderr/exit code/duration. The executor sits behind a `Sandbox`
interface so it can move to gVisor or a MicroVM without touching the domain. Scope is
deliberately limited to the safe-execution core: no platform, no accounts.

Status: reference project. Bug fixes and hardening are welcome; new features are not
planned. See `README.md` for the user view and `docs/decisions/` for the why.

## Hard rules

- The domain is tested without containers or a database.
- No user code runs without CPU, memory and time limits, and without network by
  default. The default is the most restrictive sandbox.
- One container per execution, destroyed afterwards, never reused.
- The executor runs as non-root, with a read-only root filesystem and a bounded tmpfs.
- All external input is validated with pydantic at the edge: language allowlist, code
  size, and limits within safe ranges.
- Every retryable operation is idempotent by `client_request_id`.
- The API is versioned under `/v1/`.
- Every outbound call (Docker daemon, database) has an explicit timeout.
- Secrets only through env vars; `.env.example` holds no real secrets.
- Green CI (tests + lint + typecheck) is the definition of done. Small conventional commits.

## Commands

| Task | Command |
| --- | --- |
| Install | `uv sync` |
| Unit and API tests (no Docker, no DB) | `uv run pytest -m "not contract"` |
| Contract tests (real containers) | `uv run pytest -m contract` |
| Lint, format, types | `uv run ruff check . && uv run ruff format --check . && uv run mypy` |
| Run locally | `docker compose up --build -d` |

## Layout

- `src/safeexec/domain/` holds the logic and never imports FastAPI or Docker.
- `src/safeexec/adapters/` is the only place that touches Docker, Postgres or Prometheus.
- `src/safeexec/api/` is a thin `/v1` layer: validate and delegate.
- `docs/decisions/` has the ADRs. Add one when a change makes a choice someone could
  reasonably question later.
- `docs/plan/` has the original planning notes (in Spanish), kept for history.
