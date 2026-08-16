# SafeExec

Neurona de TrendBrain: plan de implementación generado desde la opportunity «sandboxing-ejecucion-segura-codigo-ia» (AI devtools). Las notas en `brain/` son la fuente de verdad de este proyecto — leelas antes de escribir código.

## Qué es
Servicio API que ejecuta código generado por IA en sandboxes aislados y efímeros, exponiendo un endpoint HTTP versionado para enviar código + lenguaje y recibir resultado (stdout/stderr/exit/tiempo) con límites estrictos de CPU, memoria, red y tiempo. El aislamiento se resuelve con contenedores efímeros orquestados desde el servicio, no con MicroVMs en Rust: el hipotálamo fija Python/FastAPI para api-service y el MVP no justifica un runtime Rust propio; se aísla el ejecutor detrás de una interfaz para poder migrar a MicroVM/gVisor sin tocar el dominio. Consciente del patrón 'feature, no producto', el alcance se limita al núcleo de ejecución segura sin construir plataforma.

## Reglas duras (innegociables)
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

## Orden de trabajo
1. Fase 0 — Bootstrap del servicio — Repo ejecutable con esqueleto api-service, observabilidad mínima y CI verde.
2. Fase 1 — Contrato de dominio y política de límites — Modelar Execution, contrato Sandbox y política de límites, testeados sin infraestructura.
3. Fase 2 — Endpoint /v1/executions con validación — Exponer el endpoint HTTP thin con validación de borde e idempotencia.
4. Fase 3 — Ejecutor real en contenedor aislado — Implementar ContainerSandbox con aislamiento y límites forzados reales.
5. Fase 4 — Endurecimiento y métricas — Métricas de ejecución, degradación con gracia y documentación de operación.

## Mapa de notas
- `brain/sandboxing-ejecucion-segura-codigo-ia-index.md` — overview y scope del MVP
- `brain/sandboxing-ejecucion-segura-codigo-ia-origin.md` — de qué evidencia sale
- `brain/sandboxing-ejecucion-segura-codigo-ia-stack.md` — stack elegido y por qué
- `brain/sandboxing-ejecucion-segura-codigo-ia-structure.md` — estructura de carpetas
- `brain/sandboxing-ejecucion-segura-codigo-ia-principles.md` — principios de código
- `brain/sandboxing-ejecucion-segura-codigo-ia-roadmap.md` — fases con criterios de aceptación
