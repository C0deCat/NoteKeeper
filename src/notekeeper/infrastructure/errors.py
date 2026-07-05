"""Infrastructure-layer errors."""

from notekeeper.application.errors import PortExecutionError


class InfrastructureError(PortExecutionError):
    """Raised when an infrastructure adapter cannot complete an operation."""
