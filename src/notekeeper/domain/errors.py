"""Domain exceptions."""


class DomainError(Exception):
    """Base class for domain failures."""


class DomainValidationError(DomainError):
    """Raised when a domain invariant is violated."""


ValidationError = DomainValidationError


class CampaignValidationError(DomainValidationError):
    """Raised when a campaign invariant is violated."""


class TranscriptValidationError(DomainValidationError):
    """Raised when a transcript invariant is violated."""


class SpeakerMappingError(DomainValidationError):
    """Raised when a speaker mapping invariant is violated."""
