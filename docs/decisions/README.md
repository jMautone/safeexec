# Architecture decisions

Short ADRs for choices someone could reasonably question later.

| # | Decision | Status |
| --- | --- | --- |
| [0001](0001-ephemeral-containers-behind-sandbox-interface.md) | Ephemeral Docker containers behind a `Sandbox` interface, not MicroVMs | Accepted |
| [0002](0002-failures-are-results.md) | Timeout, OOM and truncation are results (200), not errors | Accepted |
| [0003](0003-postgres-for-idempotency.md) | Postgres for idempotency and audit | Accepted |
| [0004](0004-code-via-readonly-bind-mount.md) | Code reaches the container through a read-only bind mount | Accepted |
