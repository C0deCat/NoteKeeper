"""Application-layer errors."""


class ApplicationError(Exception):
    """Base error for application use cases."""


class NotFoundError(ApplicationError):
    """Raised when a requested entity does not exist."""


class InvalidOperationError(ApplicationError):
    """Raised when a use case cannot be executed in the current state."""
