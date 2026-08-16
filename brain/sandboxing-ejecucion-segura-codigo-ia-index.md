---
id: sandboxing-ejecucion-segura-codigo-ia-index
title: SafeExec — overview y scope del MVP
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

## Qué es
Servicio API que ejecuta código generado por IA en sandboxes aislados y efímeros, exponiendo un endpoint HTTP versionado para enviar código + lenguaje y recibir resultado (stdout/stderr/exit/tiempo) con límites estrictos de CPU, memoria, red y tiempo. El aislamiento se resuelve con contenedores efímeros orquestados desde el servicio, no con MicroVMs en Rust: el hipotálamo fija Python/FastAPI para api-service y el MVP no justifica un runtime Rust propio; se aísla el ejecutor detrás de una interfaz para poder migrar a MicroVM/gVisor sin tocar el dominio. Consciente del patrón 'feature, no producto', el alcance se limita al núcleo de ejecución segura sin construir plataforma.

## Scope del MVP
- POST /v1/executions: recibe {language, code, stdin?, limits?}, ejecuta en sandbox efímero y devuelve {stdout, stderr, exit_code, duration_ms, timed_out, oom_killed}
- Soporte inicial de 2 lenguajes: Python y JavaScript (Node)
- Aislamiento por contenedor efímero de un solo uso: sin red por defecto, filesystem read-only + tmpfs de escritura acotado, usuario no-root
- Límites forzados: timeout de wall-clock, límite de memoria (OOM kill), límite de CPU y de tamaño de output truncado
- Idempotencia por client_request_id para reintentos de terceros
- Observabilidad día 1: logging JSON con request id, /healthz, métrica de ejecuciones y latencia
- Validación estricta del payload en el borde (pydantic v2): lenguaje permitido, tamaño máximo de código, límites dentro de rangos seguros
