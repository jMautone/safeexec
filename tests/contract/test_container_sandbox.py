"""Contract tests: run real code in real containers and verify isolation.

Skipped automatically when no Docker daemon is reachable.
"""

import docker
import pytest
from docker.errors import DockerException

from safeexec.adapters.container_sandbox import (
    CONTAINER_LABEL,
    ContainerSandbox,
    ContainerSandboxConfig,
)
from safeexec.domain.sandbox import SandboxSpec
from safeexec.models import Language, ResourceLimits

PYTHON_IMAGE = "python:3.13-slim"
NODE_IMAGE = "node:22-slim"


def _docker_available() -> bool:
    try:
        docker.from_env(timeout=3).ping()
        return True
    except DockerException:
        return False


pytestmark = [
    pytest.mark.contract,
    pytest.mark.skipif(not _docker_available(), reason="Docker daemon not available"),
]

LIMITS = ResourceLimits(timeout_ms=20_000, memory_mb=128, cpus=1.0, max_output_bytes=65_536)


@pytest.fixture(scope="module")
def sandbox() -> ContainerSandbox:
    return ContainerSandbox(
        ContainerSandboxConfig(
            images={Language.PYTHON: PYTHON_IMAGE, Language.JAVASCRIPT: NODE_IMAGE},
            daemon_timeout_seconds=30.0,
        )
    )


def _spec(code: str, *, language: Language = Language.PYTHON, stdin: str | None = None,
          limits: ResourceLimits = LIMITS) -> SandboxSpec:  # fmt: skip
    return SandboxSpec(language=language, code=code, stdin=stdin, limits=limits)


async def test_python_hello_world(sandbox: ContainerSandbox) -> None:
    result = await sandbox.run(_spec("print('hello from sandbox')"))
    assert result.exit_code == 0
    assert result.stdout == "hello from sandbox\n"
    assert result.timed_out is False
    assert result.oom_killed is False


async def test_javascript_hello_world(sandbox: ContainerSandbox) -> None:
    result = await sandbox.run(
        _spec("console.log('hello from node')", language=Language.JAVASCRIPT)
    )
    assert result.exit_code == 0
    assert result.stdout == "hello from node\n"


async def test_stdin_is_delivered(sandbox: ContainerSandbox) -> None:
    result = await sandbox.run(_spec("print(input()[::-1])", stdin="abcdef\n"))
    assert result.exit_code == 0
    assert result.stdout == "fedcba\n"


async def test_runs_as_non_root_user(sandbox: ContainerSandbox) -> None:
    result = await sandbox.run(_spec("import os; print(os.getuid())"))
    assert result.exit_code == 0
    assert result.stdout.strip() != "0"


async def test_network_access_is_blocked(sandbox: ContainerSandbox) -> None:
    code = "import socket\ns = socket.socket()\ns.settimeout(3)\ns.connect(('1.1.1.1', 443))\n"
    result = await sandbox.run(_spec(code))
    assert result.exit_code != 0


async def test_filesystem_is_read_only_except_tmp(sandbox: ContainerSandbox) -> None:
    code = (
        "import pathlib\n"
        "pathlib.Path('/tmp/scratch').write_text('ok')\n"
        "try:\n"
        "    pathlib.Path('/etc/pwned').write_text('nope')\n"
        "except OSError:\n"
        "    print('denied')\n"
    )
    result = await sandbox.run(_spec(code))
    assert result.exit_code == 0
    assert result.stdout == "denied\n"


async def test_timeout_kills_execution(sandbox: ContainerSandbox) -> None:
    limits = ResourceLimits(timeout_ms=2_000, memory_mb=128, cpus=1.0, max_output_bytes=65_536)
    result = await sandbox.run(_spec("while True: pass", limits=limits))
    assert result.timed_out is True
    assert result.exit_code is None


async def test_memory_hog_is_oom_killed(sandbox: ContainerSandbox) -> None:
    limits = ResourceLimits(timeout_ms=20_000, memory_mb=64, cpus=1.0, max_output_bytes=65_536)
    result = await sandbox.run(_spec("x = bytearray(512 * 1024 * 1024)", limits=limits))
    assert result.oom_killed is True
    assert result.exit_code != 0


async def test_oversized_output_is_truncated_and_flagged(sandbox: ContainerSandbox) -> None:
    limits = ResourceLimits(timeout_ms=20_000, memory_mb=128, cpus=1.0, max_output_bytes=1_024)
    result = await sandbox.run(_spec("print('x' * 100_000)", limits=limits))
    assert result.stdout_truncated is True
    assert len(result.stdout.encode()) <= 1_024


async def test_container_is_always_removed(sandbox: ContainerSandbox) -> None:
    await sandbox.run(_spec("print('bye')"))
    client = docker.from_env(timeout=10)
    leftovers = client.containers.list(all=True, filters={"label": CONTAINER_LABEL})
    assert leftovers == []
