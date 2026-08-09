"""Speaker-mapping record builders for processing workflows."""

from notekeeper.application.results import PreparedAudioResult, SpeakerMappingRecord
from notekeeper.domain import ProcessingJobId, SpeakerMapping, TranscriptId


def build_automatic_mapping_records(
    *,
    job_id: ProcessingJobId,
    transcript_id: TranscriptId,
    mappings: tuple[SpeakerMapping, ...],
    prepared_audio: PreparedAudioResult,
) -> tuple[SpeakerMappingRecord, ...]:
    diagnostics = {
        "prepared_audio_artifact_uri": prepared_audio.audio_artifact.uri,
        "prepared_audio_manifest_uri": prepared_audio.manifest_artifact.uri,
        "voice_sample_range_count": len(prepared_audio.voice_sample_ranges),
    }
    return tuple(
        SpeakerMappingRecord(
            job_id=job_id,
            transcript_id=transcript_id,
            mapping=mapping,
            diagnostics=diagnostics,
        )
        for mapping in mappings
    )


def build_review_mapping_records(
    *,
    job_id: ProcessingJobId,
    transcript_id: TranscriptId,
    mappings: tuple[SpeakerMapping, ...],
    warning_count: int,
) -> tuple[SpeakerMappingRecord, ...]:
    return tuple(
        SpeakerMappingRecord(
            job_id=job_id,
            transcript_id=transcript_id,
            mapping=mapping,
            diagnostics={"warning_count": warning_count, "review_submission": True},
        )
        for mapping in mappings
    )


__all__ = ["build_automatic_mapping_records", "build_review_mapping_records"]

