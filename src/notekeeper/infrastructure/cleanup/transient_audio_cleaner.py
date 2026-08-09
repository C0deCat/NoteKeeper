"""Cleanup of transient audio created by processing jobs."""

from __future__ import annotations

from pathlib import Path

from notekeeper.application.ports import TransientAudioCleaner
from notekeeper.domain import CampaignId, ProcessingJobId
from notekeeper.infrastructure.filesystem.storage import LocalCampaignArtifactStorage
from notekeeper.infrastructure.filesystem.utils import safe_name

from .utils import remove_owned_path


class LocalTransientAudioCleaner(TransientAudioCleaner):
    def __init__(
        self,
        storage: LocalCampaignArtifactStorage,
        processing_work_root: str | Path,
    ) -> None:
        self._storage = storage
        self._processing_work_root = Path(processing_work_root)

    def clean(self, campaign_id: CampaignId, job_id: ProcessingJobId) -> None:
        campaign_name = safe_name(str(campaign_id), "campaign_id")
        job_name = safe_name(str(job_id), "job_id")
        remove_owned_path(
            self._storage.path_for_uri(
                f"{campaign_name}/records/transient/{job_name}",
            ),
            self._storage.storage_root,
            label="transient audio",
        )
        remove_owned_path(
            self._processing_work_root / campaign_name / job_name,
            self._processing_work_root,
            label="transient audio",
        )

    def clean_stale(self) -> None:
        storage_root = self._storage.storage_root
        if storage_root.is_dir():
            for transient_root in storage_root.glob("*/records/transient"):
                remove_owned_path(transient_root, storage_root, label="transient audio")
        remove_owned_path(
            self._processing_work_root,
            self._processing_work_root,
            label="transient audio",
        )
