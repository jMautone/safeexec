# 0001. Ephemeral Docker containers behind a `Sandbox` interface

- Status: Accepted
- Date: 2026-08-16

## Context

AI-generated code has to run isolated, with hard limits. The strongest options
(Firecracker MicroVMs, as used by E2B and microsandbox) need KVM and their own
runtime. The MVP has to run on a laptop and on a standard CI runner.

## Decision

Run each execution in a fresh Docker container, hardened: non-root, no network,
read-only rootfs plus a bounded tmpfs, no swap, CPU and pids caps, all capabilities
dropped, `no-new-privileges`, wall-clock kill, forced removal. The executor implements
a `Sandbox` protocol defined in the domain; the domain never imports Docker. gVisor
(`runsc`) can be switched on by config.

## Consequences

- Works anywhere Docker runs, and the contract tests run on GitHub's runners.
- Containers share the host kernel, so isolation is weaker than a MicroVM. The README
  says so and points to gVisor or a MicroVM-backed `Sandbox` for public exposure.
- Access to the Docker socket is root-equivalent: the API host is part of the trust
  boundary.
