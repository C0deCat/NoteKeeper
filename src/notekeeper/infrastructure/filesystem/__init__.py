"""Filesystem infrastructure adapters."""

from .metadata import LocalAudioMetadataReader
from .prepared_audio_manifest_store import LocalPreparedAudioManifestStore
from .scanner import LocalCampaignFolderScanner
from .storage import LocalCampaignArtifactStorage

__all__ = [
    "LocalAudioMetadataReader",
    "LocalCampaignArtifactStorage",
    "LocalCampaignFolderScanner",
    "LocalPreparedAudioManifestStore",
]
