"""Shared CLI command helpers."""

from __future__ import annotations

from collections.abc import Callable

import typer

from notekeeper.application import (
    ApplicationError,
    InspectAudioMetadataCommand,
    ManualSpeakerMappingCommand,
)
from notekeeper.domain import AudioMetadata, DomainError, JobStatus

from ..contracts import InterfaceRuntime

RuntimeFactory = Callable[[], InterfaceRuntime]


def run(action: Callable[[], None]) -> None:
    try:
        action()
    except (ApplicationError, DomainError, ValueError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


def inspect_audio(
    runtime: InterfaceRuntime,
    artifact_uri: str,
    artifact_kind: str,
) -> AudioMetadata:
    return runtime.use_cases.inspect_audio_metadata.execute(
        InspectAudioMetadataCommand(
            artifact_uri=artifact_uri,
            artifact_kind=artifact_kind,
        ),
    ).metadata


def parse_mapping(value: str) -> ManualSpeakerMappingCommand:
    anonymous_label, participant_id = _split_review_value(
        value,
        expected="SPEAKER_00=participant-id",
        target="participant id",
    )

    return ManualSpeakerMappingCommand(
        anonymous_label=anonymous_label,
        participant_id=participant_id,
        confidence=1.0,
    )


def parse_label_mapping(value: str) -> ManualSpeakerMappingCommand:
    anonymous_label, named_label = _split_review_value(
        value,
        expected="SPEAKER_00=label",
        target="label",
    )
    return ManualSpeakerMappingCommand(
        anonymous_label=anonymous_label,
        named_label=named_label,
        confidence=1.0,
    )


def parse_keep_mapping(value: str) -> ManualSpeakerMappingCommand:
    anonymous_label = value.strip()
    if not anonymous_label:
        raise ValueError("keep must include a speaker label")
    return ManualSpeakerMappingCommand(
        anonymous_label=anonymous_label,
        named_label=anonymous_label,
        confidence=1.0,
    )


def _split_review_value(
    value: str,
    *,
    expected: str,
    target: str,
) -> tuple[str, str]:
    try:
        anonymous_label, resolved_value = value.split("=", 1)
    except ValueError as exc:
        raise ValueError(f"mapping must use {expected} form") from exc

    anonymous_label = anonymous_label.strip()
    resolved_value = resolved_value.strip()
    if not anonymous_label or not resolved_value:
        raise ValueError(f"mapping must include speaker label and {target}")
    return anonymous_label, resolved_value


def echo_campaign(campaign) -> None:
    typer.echo(f"id={campaign.id} name={campaign.name}")


def echo_participant(participant) -> None:
    typer.echo(f"id={participant.id} name={participant.display_name}")


def echo_audio_track(audio_track) -> None:
    title = audio_track.title or audio_track.artifact.uri
    typer.echo(
        " ".join(
            (
                f"audio_track id={audio_track.id}",
                f"title={title}",
                f"uri={audio_track.artifact.uri}",
                f"duration={duration(audio_track.metadata)}",
            ),
        ),
    )


def echo_job(job) -> None:
    parts = [
        f"job id={job.id}",
        f"status={status(job.status)}",
        f"audio_track={job.audio_track_id}",
    ]
    if job.transcript_id is not None:
        parts.append(f"transcript={job.transcript_id}")
    if job.recap_id is not None:
        parts.append(f"recap={job.recap_id}")
    if job.error_message:
        parts.append(f"error={job.error_message}")
    typer.echo(" ".join(parts))


def echo_sync_result(result) -> None:
    typer.echo(f"campaign id={result.campaign.id} name={result.campaign.name}")
    typer.echo(f"participants_created={result.participants_created}")
    typer.echo(f"voice_samples_added={result.voice_samples_added}")
    typer.echo(f"voice_samples_updated={result.voice_samples_updated}")
    typer.echo(f"voice_samples_deleted={result.voice_samples_deleted}")
    typer.echo(f"audio_tracks_added={result.audio_tracks_added}")
    typer.echo(f"audio_tracks_updated={result.audio_tracks_updated}")
    typer.echo(f"audio_tracks_deleted={result.audio_tracks_deleted}")
    typer.echo(f"audio_tracks_normalized={result.audio_tracks_normalized}")
    typer.echo(f"bytes_freed={result.bytes_freed}")
    for warning in result.cleanup_warnings:
        typer.echo(f"cleanup_warning={warning}", err=True)
    typer.echo(f"pending_jobs_deleted={result.pending_jobs_deleted}")


def echo_metadata(metadata: AudioMetadata) -> None:
    typer.echo(f"duration={duration(metadata)}")
    if metadata.format:
        typer.echo(f"format={metadata.format}")
    if metadata.codec:
        typer.echo(f"codec={metadata.codec}")
    if metadata.sample_rate_hz:
        typer.echo(f"sample_rate_hz={metadata.sample_rate_hz}")
    if metadata.channels:
        typer.echo(f"channels={metadata.channels}")
    if metadata.file_size_bytes is not None:
        typer.echo(f"file_size_bytes={metadata.file_size_bytes}")


def duration(metadata: AudioMetadata) -> str:
    return f"{metadata.duration_seconds:.2f}s"


def status(job_status: JobStatus) -> str:
    return job_status.value
