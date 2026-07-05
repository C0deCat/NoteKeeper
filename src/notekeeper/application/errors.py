"""Application-layer errors."""


class ApplicationError(Exception):
    """Base error for application use cases."""


class PortExecutionError(ApplicationError):
    """Raised when a port implementation cannot complete an operation."""


class NotFoundError(ApplicationError):
    """Raised when a requested entity does not exist."""


class InvalidOperationError(ApplicationError):
    """Raised when a use case cannot be executed in the current state."""
