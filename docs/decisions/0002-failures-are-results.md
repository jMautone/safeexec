# 0002. Timeout, OOM and truncation are results, not errors

- Status: Accepted
- Date: 2026-08-16

## Context

The main client is an LLM loop: write code, run it, read what happened, fix it. If a
timeout came back as a 5xx, the client would have to treat it as an infrastructure
failure and could not feed it to the model.

## Decision

`timed_out`, `oom_killed`, `stdout_truncated` and `stderr_truncated` are fields of a
200 response. HTTP errors are reserved for problems with the request (422), capacity
(429) and the backend (503).

## Consequences

- Clients get one shape for every outcome the code itself caused.
- Clients must check the flags; a 200 does not mean the program succeeded.
