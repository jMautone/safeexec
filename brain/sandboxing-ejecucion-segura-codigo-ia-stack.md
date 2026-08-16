---
id: sandboxing-ejecucion-segura-codigo-ia-stack
title: SafeExec — stack elegido y por qué
type: neuron-plan
market: AI devtools
created: '2026-08-16'
updated: '2026-08-16'
sources:
- 170421160e80ac8c
- 278104a174355bd6
tags: []
base_confidence: 0.8
half_life_days: 365
last_reinforced: '2026-08-16'
provenance:
  scope: M
  ref: null
links:
- to: sandboxing-ejecucion-segura-codigo-ia
  type: derived_from
---

- **Framework HTTP:** Python 3.13 + FastAPI + pydantic v2 (async) — Estándar del hipotálamo para api-service; async encaja con orquestar ejecuciones concurrentes esperando I/O de contenedores.
- **Motor de aislamiento:** Contenedores efímeros vía Docker SDK (con opción gVisor/runsc como runtime endurecido) detrás de una interfaz Sandbox — El hipotálamo fija Python/FastAPI y el MVP no justifica un runtime MicroVM en Rust; el contenedor efímero da aislamiento suficiente y se abstrae para migrar a Firecracker/gVisor sin tocar el dominio.
- **Persistencia de resultados/idempotencia:** Postgres + SQLAlchemy 2 + alembic — Estándar del dominio; almacena claves de idempotencia y auditoría de ejecuciones.
- **Config:** pydantic-settings desde env — Secretos y límites tipados desde entorno, nunca en código.
- **Testing:** pytest + httpx AsyncClient con Sandbox fake inyectado — Permite testear dominio y API sin levantar contenedores reales; contract tests separados para el ejecutor real.
- **Deploy:** Dockerfile propio + docker compose (dev) — Mismo runtime local y prod; requiere acceso controlado al daemon/host para lanzar sandboxes.
