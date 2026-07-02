"""Local filesystem artifact storage."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from notekeeper.domain import ArtifactRef, CampaignId

from ..errors import InfrastructureError
from .utils import (
    available_path,
    ensure_within_root,
    safe_name,
    safe_relative_name,
    safe_uri_parts,
)


CAMPAIGN_FOLDERS = ("players", "records", "transcripts", "recaps")


class LocalCampaignArtifactStorage:
    def __init__(self, storage_root: str | Path) -> None:
        self._storage_root = Path(storage_root)

    @property
    def storage_root(self) -> Path:
        return self._storage_root

    def ensure_campaign_layout(self, campaign_id: CampaignId) -> None:
        campaign_path = self.campaign_path(campaign_id)
        for folder in CAMPAIGN_FOLDERS:
            (campaign_path / folder).mkdir(parents=True, exist_ok=True)

    def campaign_path(self, campaign_id: CampaignId) -> Path:
        return self._storage_root / safe_name(str(campaign_id), "campaign_id")

    def player_path(self, campaign_id: CampaignId, player_name: str) -> Path:
        return (
            self.campaign_path(campaign_id)
            / "players"
            / safe_name(player_name, "player_name")
        )

    def path_for_uri(self, uri: str) -> Path:
        parts = safe_uri_parts(uri)
        candidate = self._storage_root.joinpath(*parts)
        return ensure_within_root(candidate, self._storage_root)

    def artifact_path(self, artifact: ArtifactRef) -> Path:
        if artifact.kind != "file":
            raise InfrastructureError(f"unsupported artifact kind: {artifact.kind}")
        return self.path_for_uri(artifact.uri)

    def uri_for_path(self, path: str | Path) -> str:
        resolved_path = Path(path).resolve(strict=False)
        resolved_root = self._storage_root.resolve(strict=False)
        try:
            relative = resolved_path.relative_to(resolved_root)
        except ValueError as exc:
            raise InfrastructureError("path is outside storage root") from exc
        return relative.as_posix()

    def import_file(
        self,
        *,
        campaign_id: CampaignId,
        folder: str,
        source_path: str | Path,
        player_name: str | None = None,
    ) -> ArtifactRef:
        if folder not in CAMPAIGN_FOLDERS:
            raise InfrastructureError(f"unknown campaign folder: {folder}")
        if folder == "players" and player_name is None:
            raise InfrastructureError("player_name is required for player artifacts")

        self.ensure_campaign_layout(campaign_id)
        source = Path(source_path)
        if not source.is_file():
            raise InfrastructureError(f"source file does not exist: {source}")

        if folder == "players":
            target_dir = self.player_path(campaign_id, player_name or "")
        else:
            target_dir = self.campaign_path(campaign_id) / folder
        target_dir.mkdir(parents=True, exist_ok=True)

        target = available_path(target_dir / source.name)
        shutil.copy2(source, target)
        return ArtifactRef(uri=self.uri_for_path(target), kind="file")

    def save_text(
        self,
        *,
        suggested_name: str,
        content: str,
        media_type: str,
    ) -> ArtifactRef:
        target = self.path_for_uri(suggested_name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return ArtifactRef(uri=self.uri_for_path(target), kind="file")

    def save_campaign_text(
        self,
        *,
        campaign_id: CampaignId,
        folder: str,
        suggested_name: str,
        content: str,
        media_type: str,
    ) -> ArtifactRef:
        if folder not in CAMPAIGN_FOLDERS:
            raise InfrastructureError(f"unknown campaign folder: {folder}")

        self.ensure_campaign_layout(campaign_id)
        target = self.campaign_path(campaign_id) / folder / safe_relative_name(
            suggested_name,
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return ArtifactRef(uri=self.uri_for_path(target), kind="file")

    def save_json_payload(
        self,
        *,
        campaign_id: CampaignId,
        folder: str,
        suggested_name: str,
        payload: dict[str, Any],
    ) -> ArtifactRef:
        content = json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)
        return self.save_campaign_text(
            campaign_id=campaign_id,
            folder=folder,
            suggested_name=suggested_name,
            content=content,
            media_type="application/json",
        )

    def read_text(self, artifact: ArtifactRef) -> str:
        return self.artifact_path(artifact).read_text(encoding="utf-8")

    def read_json_payload(self, artifact_uri: str) -> dict[str, Any]:
        path = self.path_for_uri(artifact_uri)
        return json.loads(path.read_text(encoding="utf-8"))
