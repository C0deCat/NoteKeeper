"""Internal WhisperX adapter protocols."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from notekeeper.domain import ArtifactRef, CampaignId, TranscriptId


class WhisperXRunner(Protocol):
    def run(
        self,
        audio_path: Path,
        *,
        model_name: str,
        device: str,
        compute_type: str,
        batch_size: int,
        language: str | None,
        alignment_enabled: bool,
        alignment_model_name: str | None,
        alignment_model_dir: Path | None,
        alignment_model_cache_only: bool,
        diarization_enabled: bool,
        diarization_model_name: str | None,
        diarization_cache_dir: Path | None,
        hf_token: str | None,
        fill_nearest: bool,
    ) -> dict[str, Any]: ...


class WhisperXPayloadStore(Protocol):
    def payload_uri_for_transcript(
        self,
        *,
        campaign_id: CampaignId,
        transcript_id: TranscriptId,
    ) -> str: ...

    def save(
        self,
        *,
        campaign_id: CampaignId,
        transcript_id: TranscriptId,
        payload: dict[str, Any],
    ) -> ArtifactRef: ...

    def read(self, artifact: ArtifactRef) -> dict[str, Any]: ...


__all__ = ["WhisperXPayloadStore", "WhisperXRunner"]
