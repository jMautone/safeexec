"""Resource limit policy: safe defaults, hard maximums, actionable rejections."""

from dataclasses import dataclass

from safeexec.domain.errors import LimitsOutOfRangeError
from safeexec.models import LimitOverrides, ResourceLimits

MIN_TIMEOUT_MS = 100
MIN_MEMORY_MB = 16
MIN_CPUS = 0.1
MIN_OUTPUT_BYTES = 1_024


@dataclass(frozen=True, slots=True)
class LimitsPolicy:
    defaults: ResourceLimits
    maximums: ResourceLimits

    def resolve(self, overrides: LimitOverrides) -> ResourceLimits:
        return ResourceLimits(
            timeout_ms=self._check(
                "timeout_ms",
                overrides.timeout_ms,
                self.defaults.timeout_ms,
                MIN_TIMEOUT_MS,
                self.maximums.timeout_ms,
            ),
            memory_mb=self._check(
                "memory_mb",
                overrides.memory_mb,
                self.defaults.memory_mb,
                MIN_MEMORY_MB,
                self.maximums.memory_mb,
            ),
            cpus=self._check(
                "cpus",
                overrides.cpus,
                self.defaults.cpus,
                MIN_CPUS,
                self.maximums.cpus,
            ),
            max_output_bytes=self._check(
                "max_output_bytes",
                overrides.max_output_bytes,
                self.defaults.max_output_bytes,
                MIN_OUTPUT_BYTES,
                self.maximums.max_output_bytes,
            ),
        )

    @staticmethod
    def _check[T: (int, float)](
        name: str, override: T | None, default: T, minimum: T, maximum: T
    ) -> T:
        value = default if override is None else override
        if not minimum <= value <= maximum:
            raise LimitsOutOfRangeError(
                f"{name} must be between {minimum} and {maximum}, got {value}; "
                f"omit it to use the default of {default}"
            )
        return value
