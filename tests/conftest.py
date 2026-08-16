import pytest

from safeexec.domain.concurrency import ConcurrencyLimiter
from safeexec.domain.limits import LimitsPolicy
from safeexec.domain.service import ExecutionService
from safeexec.models import ResourceLimits
from tests.fakes import FakeSandbox, InMemoryExecutionRepository

DEFAULT_LIMITS = ResourceLimits(timeout_ms=5_000, memory_mb=128, cpus=0.5, max_output_bytes=65_536)
MAX_LIMITS = ResourceLimits(timeout_ms=30_000, memory_mb=512, cpus=2.0, max_output_bytes=1_048_576)


@pytest.fixture
def limits_policy() -> LimitsPolicy:
    return LimitsPolicy(defaults=DEFAULT_LIMITS, maximums=MAX_LIMITS)


@pytest.fixture
def fake_sandbox() -> FakeSandbox:
    return FakeSandbox()


@pytest.fixture
def repository() -> InMemoryExecutionRepository:
    return InMemoryExecutionRepository()


@pytest.fixture
def service(
    fake_sandbox: FakeSandbox,
    repository: InMemoryExecutionRepository,
    limits_policy: LimitsPolicy,
) -> ExecutionService:
    return ExecutionService(
        sandbox=fake_sandbox,
        repository=repository,
        limits_policy=limits_policy,
        limiter=ConcurrencyLimiter(2),
    )
