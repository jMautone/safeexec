---
id: sandboxing-ejecucion-segura-codigo-ia-implementation
title: SafeExec — estado de implementación y decisiones tomadas
type: neuron-implementation
market: AI devtools
created: '2026-08-16'
updated: '2026-08-16'
sources: []
tags: []
base_confidence: 0.9
half_life_days: 180
last_reinforced: '2026-08-16'
provenance:
  scope: M
  ref: null
links:
- to: sandboxing-ejecucion-segura-codigo-ia-index
  type: implements
- to: sandboxing-ejecucion-segura-codigo-ia-roadmap
  type: implements
---

## Estado

Las 5 fases del roadmap están implementadas (2026-08-16). El repo es un servicio
FastAPI ejecutable con CI, tests en verde (30 unit/API sin infraestructura + 10
contract tests del ejecutor real) y `mypy --strict` + `ruff` limpios.

## Qué se construyó

- `POST /v1/executions` acepta `{language, code, stdin?, limits?, client_request_id?}`
  y devuelve `{id, stdout, stderr, exit_code, duration_ms, timed_out, oom_killed,
  stdout_truncated, stderr_truncated, created_at}`. Timeout/OOM/truncado se modelan
  como resultado (200), no como error.
- Dominio puro (`src/safeexec/domain/`): contrato `Sandbox` (Protocol), `LimitsPolicy`
  con defaults seguros + máximos duros y rechazo accionable, `ExecutionService`
  (idempotencia → límites → slot de concurrencia → sandbox → persistencia → métricas),
  `ConcurrencyLimiter` que lanza `CapacityExceededError` (→ 429 + Retry-After).
  Sin imports de FastAPI ni Docker; se testea con `FakeSandbox` + repo en memoria.
- `ContainerSandbox` (adapter, único módulo que toca el SDK de Docker): contenedor
  efímero de un solo uso con no-root (65534), `network_disabled`, rootfs read-only,
  tmpfs /tmp acotado (32m), `mem_limit`+`memswap_limit` iguales (sin swap),
  `nano_cpus`, `pids_limit=64`, `cap_drop=ALL`, `no-new-privileges`, kill por
  wall-clock timeout, remove forzado en `finally`, timeout explícito en toda llamada
  al daemon. El código entra por bind-mount read-only de un workdir temporal; stdin
  por redirección de archivo. Soporta `runtime=runsc` (gVisor) por config.
- Idempotencia: unique constraint sobre `client_request_id` en Postgres; el repo
  resuelve la carrera devolviendo el resultado ya almacenado (el primero gana).
- Observabilidad: logs JSON con request_id (header `x-request-id` propagado/generado),
  `/healthz`, `/metrics` Prometheus (`safeexec_executions_total{language,outcome}`,
  `safeexec_execution_duration_seconds{language}`).
- Deploy: Dockerfile + docker compose (app + Postgres 16); el app monta el socket del
  daemon y un workdir base compartido host↔app para que el daemon vea los bind-mounts
  (sandboxes como contenedores hermanos). Migración alembic 0001 con downgrade limpio.
- CI (GitHub Actions): job `checks` (ruff + mypy + pytest sin contract) y job
  `contract` (Postgres service, alembic upgrade/downgrade/upgrade, contract tests
  con el daemon Docker del runner).

## Decisiones no obvias (y por qué)

- **Código dentro del sandbox por bind-mount ro, no `docker cp` ni stdin attach**:
  `put_archive` choca con rootfs read-only y tmpfs shadowing; attach de socket es
  frágil en docker-py. Costo: el daemon debe compartir filesystem con el servicio
  (documentado en README/runbook como requisito de host).
- **Timeout de wall-clock implementado con `container.wait(timeout=...)`** del lado
  cliente + kill: mantiene el enforcement fuera del código de usuario. Un error de
  conexión al daemon durante el wait se reporta como timeout (conservador).
- **stdlib `docker` SDK es sync**: se aísla con `asyncio.to_thread` dentro del
  adapter; el dominio permanece async puro.
- **Métricas por Protocol en dominio** (`ExecutionMetrics`) con adapter Prometheus
  singleton (`lru_cache`) para evitar doble registro en el registry global.
- **Rangos de límites**: pydantic en el borde solo valida forma/positividad; los
  rangos los valida `LimitsPolicy` en dominio para que el mensaje accionable y los
  máximos configurables vivan en un solo lugar.
- **Python 3.13 fijado** via `.python-version` (uv); el runner local tenía 3.14 y
  uv resuelve el intérprete correcto.

## Deuda conocida / próximos pasos

- Rate limiting por cliente y auth (API keys) quedan fuera del MVP a propósito.
- Contract tests corren solo con daemon disponible (skip automático si no).
- Evaluar gVisor/`runsc` en el host antes de exponer público (config ya lo soporta).
- La latencia de arranque de contenedor (~300ms+) no satisface casos "milisegundos";
  si el uso lo exige, implementar `Sandbox` sobre Firecracker/MicroVM sin tocar dominio.

## Cómo verificar

```
uv sync && uv run pytest -m "not contract" && uv run ruff check . && uv run mypy
uv run pytest -m contract        # con Docker corriendo
docker compose up --build        # luego: curl localhost:8000/healthz
```
