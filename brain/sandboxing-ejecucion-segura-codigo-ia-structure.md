---
id: sandboxing-ejecucion-segura-codigo-ia-structure
title: SafeExec — estructura de carpetas
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

```
src/safeexec/api/ (routers /v1 thin: validan y delegan) · src/safeexec/domain/ (política de límites, decisión idempotencia, contrato Sandbox, sin FastAPI ni Docker) · src/safeexec/adapters/ (ContainerSandbox con Docker/gVisor, repositorio Postgres) · src/safeexec/models.py (schemas entrada/salida + entidad Execution) · src/safeexec/config.py (settings env) · tests/ (unit dominio con FakeSandbox, api con Depends override, contract del ejecutor real)
```
