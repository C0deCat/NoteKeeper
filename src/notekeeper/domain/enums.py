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


class ProcessingStage(str, Enum):
    NORMALIZING_AUDIO = "normalizing_audio"
    CONCATENATING_AUDIO = "concatenating_audio"
    LOADING_TRANSCRIPTION_MODEL = "loading_transcription_model"
    TRANSCRIBING = "transcribing"
    LOADING_ALIGNMENT_MODEL = "loading_alignment_model"
    ALIGNING_TRANSCRIPT = "aligning_transcript"
    LOADING_DIARIZATION_MODEL = "loading_diarization_model"
    DIARIZING_SPEAKERS = "diarizing_speakers"
    MAPPING_SPEAKERS = "mapping_speakers"
    GENERATING_RECAP = "generating_recap"
