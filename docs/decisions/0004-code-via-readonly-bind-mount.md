# 0004. Code reaches the container through a read-only bind mount

- Status: Accepted
- Date: 2026-08-16

## Context

The code and stdin have to get into a container whose root filesystem is read-only.
`put_archive` conflicts with the read-only rootfs and tmpfs shadowing, and attaching
to the container's stdin is fragile in docker-py.

## Decision

Write `main.py`/`main.js` and `stdin` to a per-execution temp dir and bind-mount it
read-only at `/sandbox`. The command is `exec <interpreter> /sandbox/<file> < /sandbox/stdin`.

## Consequences

- Simple and robust; the code cannot modify its own inputs.
- The Docker daemon must see the same path as the API. When the API runs in a
  container, the workdir base is bind-mounted host↔app at the same path
  (`docker-compose.yml` does it).
