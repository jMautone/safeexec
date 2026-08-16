"""Ephemeral, single-use Docker container sandbox.

Boundary with the untyped Docker SDK; this is the only module allowed to
touch it. Requirements enforced here (see brain/ hard rules): non-root user,
no network, read-only rootfs with a bounded tmpfs, hard CPU/memory limits,
wall-clock timeout with kill, single-use container always removed.

The per-execution workdir is bind-mounted read-only into the container, so
the Docker daemon must see the same filesystem path as this process (when the
API itself runs in a container, bind-mount the workdir base from the host).
"""

import asyncio
import contextlib
import logging
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import docker
import requests
from docker.errors import APIError, DockerException, ImageNotFound

from safeexec.domain.errors import SandboxUnavailableError
from safeexec.domain.sandbox import SandboxResult, SandboxSpec
from safeexec.models import Language, ResourceLimits

logger = logging.getLogger(__name__)

_INTERPRETERS: Mapping[Language, str] = {
    Language.PYTHON: "python3",
    Language.JAVASCRIPT: "node",
}
_FILENAMES: Mapping[Language, str] = {
    Language.PYTHON: "main.py",
    Language.JAVASCRIPT: "main.js",
}

CONTAINER_LABEL = "safeexec.managed"


@dataclass(frozen=True, slots=True)
class ContainerSandboxConfig:
    images: Mapping[Language, str]
    user: str = "65534:65534"
    runtime: str | None = None
    daemon_timeout_seconds: float = 10.0
    workdir_base: str | None = None
    tmpfs_size_mb: int = 32
    pids_limit: int = 64
    environment: Mapping[str, str] = field(
        default_factory=lambda: {"HOME": "/tmp", "PYTHONDONTWRITEBYTECODE": "1"}
    )


class ContainerSandbox:
    def __init__(self, config: ContainerSandboxConfig) -> None:
        self._config = config
        self._client: docker.DockerClient | None = None
        self._client_lock = threading.Lock()

    async def run(self, spec: SandboxSpec) -> SandboxResult:
        return await asyncio.to_thread(self._run_sync, spec)

    def _connect(self) -> docker.DockerClient:
        with self._client_lock:
            if self._client is None:
                try:
                    self._client = docker.from_env(timeout=self._config.daemon_timeout_seconds)
                except DockerException as exc:
                    raise SandboxUnavailableError(
                        "cannot reach the container daemon; ensure Docker is running "
                        "and the service has access to it"
                    ) from exc
            return self._client

    def _run_sync(self, spec: SandboxSpec) -> SandboxResult:
        client = self._connect()
        with TemporaryDirectory(prefix="safeexec-", dir=self._config.workdir_base) as workdir:
            self._write_inputs(Path(workdir), spec)
            try:
                container = self._create_container(client, spec, workdir)
            except DockerException as exc:
                raise SandboxUnavailableError(
                    "failed to create sandbox container; check daemon health and images"
                ) from exc
            try:
                return self._execute(container, spec.limits)
            finally:
                self._remove(container)

    @staticmethod
    def _write_inputs(workdir: Path, spec: SandboxSpec) -> None:
        workdir.chmod(0o755)
        code_path = workdir / _FILENAMES[spec.language]
        code_path.write_text(spec.code, encoding="utf-8")
        stdin_path = workdir / "stdin"
        stdin_path.write_text(spec.stdin or "", encoding="utf-8")
        code_path.chmod(0o644)
        stdin_path.chmod(0o644)

    def _create_container(
        self, client: docker.DockerClient, spec: SandboxSpec, workdir: str
    ) -> Any:
        image = self._config.images[spec.language]
        interpreter = _INTERPRETERS[spec.language]
        filename = _FILENAMES[spec.language]
        kwargs: dict[str, Any] = {
            "image": image,
            "command": [
                "/bin/sh",
                "-c",
                f"exec {interpreter} /sandbox/{filename} < /sandbox/stdin",
            ],
            "user": self._config.user,
            "network_disabled": True,
            "read_only": True,
            "mem_limit": f"{spec.limits.memory_mb}m",
            "memswap_limit": f"{spec.limits.memory_mb}m",
            "nano_cpus": int(spec.limits.cpus * 1_000_000_000),
            "pids_limit": self._config.pids_limit,
            "tmpfs": {"/tmp": f"rw,size={self._config.tmpfs_size_mb}m"},
            "volumes": {workdir: {"bind": "/sandbox", "mode": "ro"}},
            "security_opt": ["no-new-privileges:true"],
            "cap_drop": ["ALL"],
            "working_dir": "/tmp",
            "environment": dict(self._config.environment),
            "labels": {CONTAINER_LABEL: "true"},
            "detach": True,
        }
        if self._config.runtime is not None:
            kwargs["runtime"] = self._config.runtime
        try:
            return client.containers.create(**kwargs)
        except ImageNotFound:
            logger.info("pulling sandbox image", extra={"image": image})
            client.images.pull(image)
            return client.containers.create(**kwargs)

    def _execute(self, container: Any, limits: ResourceLimits) -> SandboxResult:
        started = time.perf_counter()
        container.start()
        timed_out, exit_code = self._wait(container, limits.timeout_ms)
        duration_ms = int((time.perf_counter() - started) * 1000)
        oom_killed = self._was_oom_killed(container)
        stdout, stdout_truncated = self._read_stream(container, limits, stdout=True)
        stderr, stderr_truncated = self._read_stream(container, limits, stdout=False)
        return SandboxResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            duration_ms=duration_ms,
            timed_out=timed_out,
            oom_killed=oom_killed,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
        )

    @staticmethod
    def _wait(container: Any, timeout_ms: int) -> tuple[bool, int | None]:
        try:
            result = container.wait(timeout=timeout_ms / 1000)
            return False, result.get("StatusCode")
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError):
            with contextlib.suppress(APIError):
                container.kill()
            return True, None

    @staticmethod
    def _was_oom_killed(container: Any) -> bool:
        try:
            container.reload()
            return bool(container.attrs["State"]["OOMKilled"])
        except DockerException:
            return False

    @staticmethod
    def _read_stream(container: Any, limits: ResourceLimits, *, stdout: bool) -> tuple[str, bool]:
        try:
            raw: bytes = container.logs(stdout=stdout, stderr=not stdout)
        except DockerException:
            return "", False
        truncated = len(raw) > limits.max_output_bytes
        return raw[: limits.max_output_bytes].decode("utf-8", errors="replace"), truncated

    @staticmethod
    def _remove(container: Any) -> None:
        try:
            container.remove(force=True)
        except DockerException:
            logger.warning("failed to remove sandbox container", extra={"container": container.id})
