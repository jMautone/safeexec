# 0003. Postgres for idempotency and audit

- Status: Accepted
- Date: 2026-08-16

## Context

Clients retry. A retried request must not run the code twice, and concurrent retries
with the same `client_request_id` must agree on one result.

## Decision

Store every execution in Postgres with a unique constraint on `client_request_id`.
The service looks the key up first; if two requests race, the insert that loses gets
an `IntegrityError` and returns the stored row. The first result wins.

## Consequences

- Correct under concurrency without locks in the service.
- A database is heavy for a v0.1; SQLite or an in-memory store would be enough for a
  single process. The repository is behind an interface, so swapping it is local to
  `adapters/`.
- Executions double as an audit log.
