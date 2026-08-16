# SafeExec

API service that executes AI-generated code inside ephemeral, locked-down sandboxes.
Send code + language to a versioned HTTP endpoint; get back stdout/stderr/exit code/
duration with strict CPU, memory, time, and network limits enforced.

Each execution runs in a **single-use container**: non-root user, no network,
read-only root filesystem with a small bounded tmpfs, hard memory/CPU caps and a
wall-clock timeout. The container is destroyed after every run, never reused. The
executor lives behind a `Sandbox` interface so it can be swapped for gVisor/MicroVMs
without touching the domain.

## Quickstart (≤3 commands)

```bash
docker compose up --build -d
```

```bash
curl -s localhost:8000/healthz
```

```bash
curl -s -X POST localhost:8000/v1/executions \
  -H 'content-type: application/json' \
  -d '{"language": "python", "code": "print(\"hello sandbox\")"}'
```

Response:

```json
{
  "id": "…",
  "language": "python",
  "stdout": "hello sandbox\n",
  "stderr": "",
  "exit_code": 0,
  "duration_ms": 312,
  "timed_out": false,
  "oom_killed": false,
  "stdout_truncated": false,
  "stderr_truncated": false,
  "created_at": "…"
}
```

## API

### `POST /v1/executions`

| Field | Type | Notes |
|---|---|---|
| `language` | `"python" \| "javascript"` | allowlist, anything else → 422 |
| `code` | string | required, ≤ 65 536 chars |
| `stdin` | string? | ≤ 16 384 chars |
| `limits` | object? | `timeout_ms`, `memory_mb`, `cpus`, `max_output_bytes` — validated against configured ranges; out-of-range → 422 with an actionable message |
| `client_request_id` | string? | idempotency key: retrying with the same id returns the stored result without re-executing |

Failure modes are modeled as results, not errors: `timed_out`, `oom_killed`, and
`*_truncated` come back in a 200 response.

Other statuses: `429` when execution capacity is exhausted (with `Retry-After`),
`503` when the container backend is unavailable.

### Observability

- `GET /healthz` — liveness.
- `GET /metrics` — Prometheus: `safeexec_executions_total{language,outcome}` and
  `safeexec_execution_duration_seconds{language}`.
- JSON logs to stdout with a per-request `request_id` (taken from or echoed to the
  `x-request-id` header).

## Development

```bash
uv sync
uv run pytest -m "not contract"   # domain + API tests, no Docker/DB needed
uv run pytest -m contract         # real executor tests, requires Docker daemon
uv run ruff check . && uv run ruff format --check . && uv run mypy
```

Domain tests use an injected `FakeSandbox` and in-memory repository — no containers
or database. Contract tests run real code in real containers and verify isolation
(network blocked, OOM kill, timeout kill, read-only fs, non-root, cleanup).

## Runbook

### Environment variables

All settings use the `SAFEEXEC_` prefix — see [.env.example](.env.example) for the
full list. Key ones:

| Variable | Default | Meaning |
|---|---|---|
| `SAFEEXEC_DATABASE_URL` | localhost Postgres | async SQLAlchemy URL |
| `SAFEEXEC_PYTHON_IMAGE` / `SAFEEXEC_NODE_IMAGE` | `python:3.13-slim` / `node:22-slim` | sandbox base images |
| `SAFEEXEC_SANDBOX_RUNTIME` | unset | set `runsc` to use gVisor as a hardened runtime |
| `SAFEEXEC_SANDBOX_WORKDIR_BASE` | system tmp | per-execution workdir base; must be daemon-visible under the same path when the API runs containerized |
| `SAFEEXEC_MAX_CONCURRENT_EXECUTIONS` | 4 | above this, requests get 429 |
| `SAFEEXEC_DEFAULT_*` / `SAFEEXEC_MAX_*` | see `.env.example` | limit policy defaults and hard caps |
| `SAFEEXEC_DOCKER_TIMEOUT_SECONDS` | 10 | timeout on every Docker daemon call |

### Host requirements for sandboxing

- A reachable Docker daemon. When the API itself runs in a container it needs
  `/var/run/docker.sock` mounted (sandboxes run as **sibling** containers) plus the
  workdir base bind-mounted host↔app at the same path (compose does both).
- Access to the daemon socket is root-equivalent: treat the API host as part of the
  sandbox trust boundary. For public exposure, evaluate gVisor (`runsc`) or a
  MicroVM-backed implementation of the `Sandbox` interface.
- Sandbox images are pulled on first use; pre-pull them to avoid first-request latency.

### Degradation behavior

- Docker daemon down → `503` with a generic actionable message (internals only in logs).
- Capacity saturated → `429` + `Retry-After`, service stays healthy.
- Every daemon call has an explicit timeout; a hung container is killed at the
  execution's wall-clock limit and always removed afterwards.

## Architecture

```
src/safeexec/
  api/        thin /v1 routers, middleware, error mapping — validate and delegate
  domain/     Sandbox contract, limits policy, idempotency, concurrency — no FastAPI, no Docker
  adapters/   ContainerSandbox (Docker SDK), Postgres repository, Prometheus metrics
  models.py   pydantic edge schemas + frozen domain entities
  config.py   pydantic-settings from env
```

Project notes and decisions live in `brain/` (source of truth for scope and rules).
