"""Domain enums."""

from enum import Enum


class SpeakerLabelKind(str, Enum):
    ANONYMOUS = "anonymous"
    NAMED = "named"


class SpeakerMappingSource(str, Enum):
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    SAMPLE_BASED = "sample_based"
    EMBEDDING_BASED = "embedding_based"


class SpeakerMappingStatus(str, Enum):
    CONFIRMED = "confirmed"
    UNCERTAIN = "uncertain"
    REJECTED = "rejected"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_FOR_REVIEW = "waiting_for_review"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class PipelineWarningKind(str, Enum):
    UNRESOLVED_SPEAKER_LABEL = "unresolved_speaker_label"
    DUPLICATE_MAPPING = "duplicate_mapping"
    UNKNOWN_PARTICIPANT = "unknown_participant"
    UNCERTAIN_MAPPING = "uncertain_mapping"
    CONFLICTING_MAPPING = "conflicting_mapping"
    MISSING_VOICE_SAMPLE = "missing_voice_sample"
