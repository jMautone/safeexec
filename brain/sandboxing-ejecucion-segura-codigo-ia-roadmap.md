---
id: sandboxing-ejecucion-segura-codigo-ia-roadmap
title: SafeExec — fases con criterios de aceptación
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

## Fase 1: Fase 0 — Bootstrap del servicio

Repo ejecutable con esqueleto api-service, observabilidad mínima y CI verde.

### Tareas
- [ ] Inicializar proyecto Python 3.13 + FastAPI + pydantic v2 con estructura por features (api/domain/adapters)
- [ ] Configurar config.py con pydantic-settings y .env.example
- [ ] Agregar logging JSON con request id, endpoint /healthz
- [ ] Configurar Dockerfile + docker compose (app + Postgres)
- [ ] Configurar CI: pytest + ruff (lint) + mypy strict; README con setup en ≤3 comandos

### Criterios de aceptación
- `docker compose up` levanta app y responde 200 en /healthz
- CI corre tests+lint+typecheck en verde sobre repo vacío de features
- Logs emiten JSON con request id por request
- mypy strict pasa sin Any fuera de adapters

## Fase 2: Fase 1 — Contrato de dominio y política de límites

Modelar Execution, contrato Sandbox y política de límites, testeados sin infraestructura.

### Tareas
- [ ] Definir models.py: ExecutionRequest, ExecutionResult, entidad Execution, enum Language
- [ ] Definir interfaz Sandbox (run(spec) -> SandboxResult) en domain
- [ ] Implementar política de límites: defaults seguros y validación de rangos
- [ ] Escribir FakeSandbox para tests
- [ ] TDD del servicio de dominio que orquesta validación → ejecución → resultado

### Criterios de aceptación
- Tests de dominio pasan usando FakeSandbox sin Docker ni DB
- Límites fuera de rango son rechazados con error accionable antes de ejecutar
- Cobertura de casos: éxito, timeout, oom, output truncado modelados como resultado

## Fase 3: Fase 2 — Endpoint /v1/executions con validación

Exponer el endpoint HTTP thin con validación de borde e idempotencia.

### Tareas
- [ ] Router /v1/executions que valida payload y delega al dominio
- [ ] Validación pydantic: allowlist de lenguajes, tamaño máximo de código, stdin
- [ ] Persistir Execution + client_request_id en Postgres (SQLAlchemy 2 + alembic)
- [ ] Idempotencia: mismo client_request_id devuelve el resultado previo
- [ ] Tests de API con httpx AsyncClient y FakeSandbox inyectado por Depends override

### Criterios de aceptación
- POST válido devuelve 200 con schema de resultado completo
- Payload inválido devuelve 422 con mensaje accionable (qué pasó + qué hacer)
- Reintento con mismo client_request_id no re-ejecuta y devuelve el mismo resultado
- Migración alembic aplica y revierte limpia

## Fase 4: Fase 3 — Ejecutor real en contenedor aislado

Implementar ContainerSandbox con aislamiento y límites forzados reales.

### Tareas
- [ ] Implementar ContainerSandbox con Docker SDK: contenedor efímero, no-root, sin red, read-only + tmpfs
- [ ] Forzar límites: --memory (OOM), --cpus, timeout wall-clock con kill, truncado de output
- [ ] Imágenes base mínimas para Python y Node
- [ ] Timeout explícito en toda llamada al daemon; manejo explícito de fallos del daemon
- [ ] Contract tests del ejecutor real: ejecutan código real y verifican aislamiento (sin red, límites aplicados)

### Criterios de aceptación
- Código que excede memoria reporta oom_killed=true sin colgar el servicio
- Código que excede tiempo reporta timed_out=true y el contenedor se destruye
- Intento de acceso a red falla dentro del sandbox
- Contenedor se elimina siempre tras la ejecución (verificado en test)
- Output que supera el límite se trunca y se señaliza

## Fase 5: Fase 4 — Endurecimiento y métricas

Métricas de ejecución, degradación con gracia y documentación de operación.

### Tareas
- [ ] Métricas: contador de ejecuciones por lenguaje/resultado y latencia
- [ ] Límite de concurrencia de sandboxes con respuesta clara al saturar (429)
- [ ] Manejo de errores del ejecutor con degradación graciosa en prod
- [ ] Runbook breve en README: variables de entorno, límites, requisitos de host para sandboxing

### Criterios de aceptación
- Métricas expuestas y verificadas en test
- Al superar concurrencia máxima responde 429 accionable, sin caídas
- Fallo del daemon devuelve error accionable sin filtrar internals
- CI completo (unit + api + contract) en verde
