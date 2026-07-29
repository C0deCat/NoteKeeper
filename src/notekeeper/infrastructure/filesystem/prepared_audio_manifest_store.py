"""Prepared-audio manifest storage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from notekeeper.application.ports import PreparedAudioManifestStore
from notekeeper.domain import ArtifactRef, CampaignId, ProcessingJobId

from ..errors import InfrastructureError
from .storage import LocalCampaignArtifactStorage
from .utils import safe_name


class LocalPreparedAudioManifestStore(PreparedAudioManifestStore):
    def __init__(self, storage: LocalCampaignArtifactStorage) -> None:
        self._storage = storage

    def manifest_uri_for_job(
        self,
        *,
        campaign_id: CampaignId,
        job_id: ProcessingJobId,
    ) -> str:
        campaign_name = safe_name(str(campaign_id), "campaign_id")
        job_name = safe_name(str(job_id), "job_id")
        return (
            f"{campaign_name}/records/manifests/"
            f"{job_name}/prepared-audio.json"
        )

    def save(
        self,
        *,
        campaign_id: CampaignId,
        job_id: ProcessingJobId,
        payload: dict[str, Any],
    ) -> ArtifactRef:
        manifest_uri = self.manifest_uri_for_job(
            campaign_id=campaign_id,
            job_id=job_id,
        )
        manifest_path = self._storage.path_for_uri(manifest_uri)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return ArtifactRef(uri=self._storage.uri_for_path(manifest_path), kind="file")

    def read(self, artifact: ArtifactRef) -> dict[str, Any]:
        path = self._storage.artifact_path(artifact)
        if not path.is_file():
            raise InfrastructureError(f"manifest artifact does not exist: {artifact.uri}")

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise InfrastructureError(
                f"could not read prepared-audio manifest: {artifact.uri}",
            ) from exc

        if not isinstance(payload, dict):
            raise InfrastructureError(
                f"prepared-audio manifest must be a JSON object: {artifact.uri}",
            )
        return payload

    def read_for_job(
        self,
        *,
        campaign_id: CampaignId,
        job_id: ProcessingJobId,
    ) -> dict[str, Any]:
        return self.read(
            ArtifactRef(
                uri=self.manifest_uri_for_job(
                    campaign_id=campaign_id,
                    job_id=job_id,
                ),
                kind="file",
            ),
        )

    def path_for_job(
        self,
        *,
        campaign_id: CampaignId,
        job_id: ProcessingJobId,
    ) -> Path:
        return self._storage.path_for_uri(
            self.manifest_uri_for_job(campaign_id=campaign_id, job_id=job_id),
        )
