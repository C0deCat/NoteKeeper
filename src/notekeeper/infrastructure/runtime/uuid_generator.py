"""UUID-backed id generator adapter."""

from uuid import uuid4

from notekeeper.application.ports import IdGenerator


class UuidGenerator(IdGenerator):
    def campaign_id(self) -> str:
        return f"campaign-{uuid4()}"

    def participant_id(self) -> str:
        return f"participant-{uuid4()}"

    def voice_sample_id(self) -> str:
        return f"voice-sample-{uuid4()}"

    def audio_track_id(self) -> str:
        return f"audio-track-{uuid4()}"

    def processing_job_id(self) -> str:
        return f"job-{uuid4()}"

    def transcript_id(self) -> str:
        return f"transcript-{uuid4()}"

    def recap_id(self) -> str:
        return f"recap-{uuid4()}"
