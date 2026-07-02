"""Filesystem infrastructure adapters."""

from .metadata import LocalAudioMetadataReader
from .scanner import LocalCampaignFolderScanner
from .storage import LocalCampaignArtifactStorage

__all__ = [
    "LocalAudioMetadataReader",
    "LocalCampaignArtifactStorage",
    "LocalCampaignFolderScanner",
]
