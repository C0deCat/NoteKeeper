"""Cleanup of transient audio created by processing jobs."""

from __future__ import annotations

import shutil
from pathlib import Path

from notekeeper.application.ports import TransientAudioCleaner
from notekeeper.domain import CampaignId, ProcessingJobId
from notekeeper.infrastructure.errors import InfrastructureError
from notekeeper.infrastructure.filesystem.storage import LocalCampaignArtifactStorage
from notekeeper.infrastructure.filesystem.utils import ensure_within_root, safe_name


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
        self._remove_path(
            self._storage.path_for_uri(
                f"{campaign_name}/records/transient/{job_name}",
            ),
            self._storage.storage_root,
        )
        self._remove_path(
            self._processing_work_root / campaign_name / job_name,
            self._processing_work_root,
        )

    def clean_stale(self) -> None:
        storage_root = self._storage.storage_root
        if storage_root.is_dir():
            for transient_root in storage_root.glob("*/records/transient"):
                self._remove_path(transient_root, storage_root)
        self._remove_path(self._processing_work_root, self._processing_work_root)

    @property
    def work_namespace(self) -> Path:
        return self._processing_work_root

    @staticmethod
    def _remove_path(path: Path, root: Path) -> None:
        ensure_within_root(path, root)
        if not path.exists() and not path.is_symlink():
            return
        if path.is_symlink():
            raise InfrastructureError("transient audio path must not be a symlink")
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        except OSError as exc:
            raise InfrastructureError(
                f"could not delete transient audio path: {path}",
            ) from exc
