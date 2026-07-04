"""Raw WhisperX payload artifact storage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from notekeeper.domain import ArtifactRef, CampaignId, TranscriptId
from notekeeper.infrastructure.errors import InfrastructureError
from notekeeper.infrastructure.filesystem.storage import LocalCampaignArtifactStorage
from notekeeper.infrastructure.filesystem.utils import safe_name


class LocalWhisperXPayloadStore:
    def __init__(self, storage: LocalCampaignArtifactStorage) -> None:
        self._storage = storage

    def payload_uri_for_transcript(
        self,
        *,
        campaign_id: CampaignId,
        transcript_id: TranscriptId,
    ) -> str:
        campaign_name = safe_name(str(campaign_id), "campaign_id")
        transcript_name = safe_name(str(transcript_id), "transcript_id")
        return f"{campaign_name}/transcripts/raw-whisperx/{transcript_name}.json"

    def save(
        self,
        *,
        campaign_id: CampaignId,
        transcript_id: TranscriptId,
        payload: dict[str, Any],
    ) -> ArtifactRef:
        payload_uri = self.payload_uri_for_transcript(
            campaign_id=campaign_id,
            transcript_id=transcript_id,
        )
        payload_path = self._storage.path_for_uri(payload_uri)
        payload_path.parent.mkdir(parents=True, exist_ok=True)
        payload_path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return ArtifactRef(uri=self._storage.uri_for_path(payload_path), kind="file")

    def read(self, artifact: ArtifactRef) -> dict[str, Any]:
        path = self._storage.artifact_path(artifact)
        if not path.is_file():
            raise InfrastructureError(
                f"WhisperX payload artifact does not exist: {artifact.uri}",
            )

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise InfrastructureError(
                f"could not read WhisperX payload: {artifact.uri}",
            ) from exc

        if not isinstance(payload, dict):
            raise InfrastructureError(
                f"WhisperX payload must be a JSON object: {artifact.uri}",
            )
        return payload

    def path_for_transcript(
        self,
        *,
        campaign_id: CampaignId,
        transcript_id: TranscriptId,
    ) -> Path:
        return self._storage.path_for_uri(
            self.payload_uri_for_transcript(
                campaign_id=campaign_id,
                transcript_id=transcript_id,
            ),
        )


__all__ = ["LocalWhisperXPayloadStore"]
