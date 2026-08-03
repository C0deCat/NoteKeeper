"""Shared Textual formatting and validation helpers."""

from __future__ import annotations

from notekeeper.application import SyncCampaignFolderResult
from notekeeper.domain import AudioMetadata, ProcessingJob

from ..contracts import RuntimeDiagnostics


def format_duration(metadata: AudioMetadata) -> str:
    return f"{metadata.duration_seconds:.2f}s"


def metadata_text(metadata: AudioMetadata) -> str:
    lines = [f"duration: {format_duration(metadata)}"]
    if metadata.format:
        lines.append(f"format: {metadata.format}")
    if metadata.codec:
        lines.append(f"codec: {metadata.codec}")
    if metadata.sample_rate_hz:
        lines.append(f"sample rate: {metadata.sample_rate_hz} Hz")
    if metadata.channels:
        lines.append(f"channels: {metadata.channels}")
    if metadata.file_size_bytes is not None:
        lines.append(f"size: {metadata.file_size_bytes} bytes")
    return "\n".join(lines)


def warnings_text(job: ProcessingJob) -> str:
    lines = [f"{warning.kind.value}: {warning.message}" for warning in job.warnings]
    if job.error_message:
        lines.append(f"error: {job.error_message}")
    return "\n".join(lines) if lines else "No warnings"


def sync_result_status(result: SyncCampaignFolderResult) -> str:
    message = (
        "Synced: "
        f"players +{result.participants_created}, "
        f"samples +{result.voice_samples_added}/~{result.voice_samples_updated}"
        f"/-{result.voice_samples_deleted}, "
        f"records +{result.audio_tracks_added}/~{result.audio_tracks_updated}"
        f"/-{result.audio_tracks_deleted}, "
        f"normalized {result.audio_tracks_normalized}, "
        f"freed {result.bytes_freed} bytes, "
        f"pending jobs -{result.pending_jobs_deleted}"
    )
    if result.cleanup_warnings:
        message = f"{message}, cleanup pending {len(result.cleanup_warnings)}"
    return message


def diagnostics_text(diagnostics: RuntimeDiagnostics) -> str:
    lines = [
        f"storage root: {diagnostics.storage_root}",
        f"sqlite path: {diagnostics.sqlite_path}",
        f"processing work root: {diagnostics.processing_work_root}",
        f"recap prompts file: {diagnostics.recap_prompts_file}",
        f"whisperx model: {diagnostics.whisperx_model_name}",
        f"whisperx device: {diagnostics.whisperx_device}",
        f"whisperx compute type: {diagnostics.whisperx_compute_type}",
        f"whisperx VAD method: {diagnostics.whisperx_vad_method}",
        f"deepseek configured: {diagnostics.deepseek_configured}",
        f"huggingface configured: {diagnostics.huggingface_configured}",
    ]
    lines.extend(f"recent: {message}" for message in diagnostics.recent_messages)
    return "\n".join(lines)
