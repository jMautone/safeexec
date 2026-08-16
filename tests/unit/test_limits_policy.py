import pytest

from safeexec.domain.errors import LimitsOutOfRangeError
from safeexec.domain.limits import LimitsPolicy
from safeexec.models import LimitOverrides
from tests.conftest import DEFAULT_LIMITS


def test_no_overrides_yields_safe_defaults(limits_policy: LimitsPolicy) -> None:
    assert limits_policy.resolve(LimitOverrides()) == DEFAULT_LIMITS


def test_overrides_within_range_are_applied(limits_policy: LimitsPolicy) -> None:
    resolved = limits_policy.resolve(LimitOverrides(timeout_ms=10_000, memory_mb=256))
    assert resolved.timeout_ms == 10_000
    assert resolved.memory_mb == 256
    assert resolved.cpus == DEFAULT_LIMITS.cpus


@pytest.mark.parametrize(
    ("overrides", "expected_field"),
    [
        (LimitOverrides(timeout_ms=60_000), "timeout_ms"),
        (LimitOverrides(timeout_ms=10), "timeout_ms"),
        (LimitOverrides(memory_mb=4_096), "memory_mb"),
        (LimitOverrides(memory_mb=1), "memory_mb"),
        (LimitOverrides(cpus=8.0), "cpus"),
        (LimitOverrides(max_output_bytes=10_000_000), "max_output_bytes"),
    ],
)
def test_out_of_range_is_rejected_with_actionable_message(
    limits_policy: LimitsPolicy, overrides: LimitOverrides, expected_field: str
) -> None:
    with pytest.raises(LimitsOutOfRangeError) as excinfo:
        limits_policy.resolve(overrides)
    message = str(excinfo.value)
    assert expected_field in message
    assert "must be between" in message
    assert "default" in message
