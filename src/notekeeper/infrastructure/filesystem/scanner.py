"""Local campaign folder scanner."""

from __future__ import annotations

from pathlib import Path

from notekeeper.application.ports import CampaignFolderScanner
from notekeeper.application.results import (
    CampaignFolderSnapshot,
    ScannedAudioTrackArtifact,
    ScannedVoiceSampleArtifact,
)
from notekeeper.domain import ArtifactRef, CampaignId

from .storage import LocalCampaignArtifactStorage


DEFAULT_AUDIO_EXTENSIONS = (
    ".aac",
    ".flac",
    ".m4a",
    ".mp3",
    ".ogg",
    ".opus",
    ".wav",
    ".webm",
)


class LocalCampaignFolderScanner(CampaignFolderScanner):
    def __init__(
        self,
        storage: LocalCampaignArtifactStorage,
        audio_extensions: tuple[str, ...] = DEFAULT_AUDIO_EXTENSIONS,
    ) -> None:
        self._storage = storage
        self._audio_extensions = tuple(extension.casefold() for extension in audio_extensions)

    def scan(self, campaign_id: CampaignId) -> CampaignFolderSnapshot:
        self._storage.ensure_campaign_layout(campaign_id)
        campaign_path = self._storage.campaign_path(campaign_id)
        return CampaignFolderSnapshot(
            campaign_id=str(campaign_id),
            voice_samples=self._scan_voice_samples(campaign_path),
            audio_tracks=self._scan_audio_tracks(campaign_path),
        )

    def _scan_voice_samples(
        self,
        campaign_path: Path,
    ) -> tuple[ScannedVoiceSampleArtifact, ...]:
        players_path = campaign_path / "players"
        scanned: list[ScannedVoiceSampleArtifact] = []
        for player_path in sorted(players_path.iterdir(), key=lambda path: path.name.casefold()):
            if not player_path.is_dir():
                continue
            for sample_path in sorted(player_path.iterdir(), key=lambda path: path.name.casefold()):
                if not self._is_audio_file(sample_path):
                    continue
                scanned.append(
                    ScannedVoiceSampleArtifact(
                        player_name=player_path.name,
                        artifact=ArtifactRef(
                            uri=self._storage.uri_for_path(sample_path),
                            kind="file",
                        ),
                    ),
                )
        return tuple(scanned)

    def _scan_audio_tracks(
        self,
        campaign_path: Path,
    ) -> tuple[ScannedAudioTrackArtifact, ...]:
        records_path = campaign_path / "records"
        scanned: list[ScannedAudioTrackArtifact] = []
        for record_path in sorted(records_path.iterdir(), key=lambda path: path.name.casefold()):
            if not self._is_audio_file(record_path):
                continue
            scanned.append(
                ScannedAudioTrackArtifact(
                    artifact=ArtifactRef(
                        uri=self._storage.uri_for_path(record_path),
                        kind="file",
                    ),
                    title=record_path.stem,
                ),
            )
        return tuple(scanned)

    def _is_audio_file(self, path: Path) -> bool:
        return path.is_file() and path.suffix.casefold() in self._audio_extensions
