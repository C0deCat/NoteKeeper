"""Artifact and campaign-folder storage ports."""

from pathlib import Path
from typing import Any, Protocol

from notekeeper.application.results import CampaignFolderSnapshot
from notekeeper.domain import ArtifactRef, CampaignId, ProcessingJobId


class ArtifactStorage(Protocol):
    def save_text(
        self,
        *,
        suggested_name: str,
        content: str,
        media_type: str,
    ) -> ArtifactRef: ...


class CampaignArtifactStorage(ArtifactStorage, Protocol):
    def ensure_campaign_layout(self, campaign_id: CampaignId) -> None: ...

    def delete_campaign(self, campaign_id: CampaignId) -> None: ...

    def artifact_exists(self, artifact: ArtifactRef) -> bool: ...

    def delete_artifact(self, artifact: ArtifactRef) -> None: ...

    def import_file(
        self,
        *,
        campaign_id: CampaignId,
        folder: str,
        source_path: str | Path,
        player_name: str | None = None,
    ) -> ArtifactRef: ...

    def save_campaign_text(
        self,
        *,
        campaign_id: CampaignId,
        folder: str,
        suggested_name: str,
        content: str,
        media_type: str,
    ) -> ArtifactRef: ...


class PreparedAudioManifestStore(Protocol):
    def manifest_uri_for_job(
        self,
        *,
        campaign_id: CampaignId,
        job_id: ProcessingJobId,
    ) -> str: ...

    def save(
        self,
        *,
        campaign_id: CampaignId,
        job_id: ProcessingJobId,
        payload: dict[str, Any],
    ) -> ArtifactRef: ...

    def read(self, artifact: ArtifactRef) -> dict[str, Any]: ...

    def read_for_job(
        self,
        *,
        campaign_id: CampaignId,
        job_id: ProcessingJobId,
    ) -> dict[str, Any]: ...


class CampaignFolderScanner(Protocol):
    def scan(self, campaign_id: CampaignId) -> CampaignFolderSnapshot: ...

