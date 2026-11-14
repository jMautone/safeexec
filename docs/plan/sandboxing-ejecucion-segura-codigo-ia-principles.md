---
id: sandboxing-ejecucion-segura-codigo-ia-principles
title: SafeExec — principios de código
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

## Principios
- Clean code: funciones < 30 líneas, una responsabilidad, nombres que declaran intención
- Tipado estricto: type hints completos, sin Any salvo frontera con SDK sin tipos aislada en adapter
- YAGNI: solo Python+JS, sin multi-tenant ni plataforma; el patrón vecino advierte que esto es una feature
- Dependencias hacia adentro: dominio no importa FastAPI ni Docker; el ejecutor es un detalle detrás de la interfaz Sandbox
- TDD: test que falla primero, implementación mínima, refactor
- Errores explícitos: sin catch vacíos; timeout/OOM se modelan como resultado, no como excepción silenciada
- Fallar ruidoso en dev, degradar con gracia en prod

## Reglas duras
- El dominio se testea sin levantar contenedores ni DB
- Ningún código de usuario corre sin límites de CPU, memoria, tiempo y sin red por defecto; el default es el sandbox más restrictivo
- Contenedor efímero de un solo uso: se destruye tras cada ejecución, jamás se reutiliza
- Ejecutor siempre como usuario no-root, filesystem read-only + tmpfs acotado
- Toda entrada externa validada con pydantic en el borde: lenguaje en allowlist, tamaño de código y límites dentro de rangos seguros
- Idempotencia por client_request_id en toda operación reintentable
- API versionada /v1/ desde el primer endpoint
- Todo llamado hacia afuera (Docker daemon, etc.) con timeout explícito
- Secretos solo por env; .env.example sin secretos reales
- CI verde (tests+lint+typecheck) es la definición de terminado; commits convencionales chicos
