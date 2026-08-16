"""Domain errors. Messages must be actionable: what happened + what to do."""


class DomainError(Exception):
    pass


class LimitsOutOfRangeError(DomainError):
    pass


class CapacityExceededError(DomainError):
    pass


class SandboxUnavailableError(DomainError):
    pass
