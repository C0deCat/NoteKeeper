"""Processing job entity."""

from dataclasses import dataclass
from datetime import datetime

from ..enums import JobStatus
from ..errors import DomainValidationError
from ..ids import AudioTrackId, CampaignId, ProcessingJobId, RecapId, TranscriptId
from ..validation import as_tuple, optional_non_empty_str
from ..value_objects import PipelineWarning


@dataclass(frozen=True, slots=True)
class ProcessingJob:
    id: ProcessingJobId
    campaign_id: CampaignId
    audio_track_id: AudioTrackId
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    transcript_id: TranscriptId | None = None
    recap_id: RecapId | None = None
    warnings: tuple[PipelineWarning, ...] = ()
    error_message: str | None = None

    def __post_init__(self) -> None:
        if self.updated_at < self.created_at:
            raise DomainValidationError("updated_at must not be earlier than created_at")

        object.__setattr__(self, "warnings", as_tuple(self.warnings, "warnings"))
        object.__setattr__(
            self,
            "error_message",
            optional_non_empty_str(self.error_message, "error_message"),
        )
