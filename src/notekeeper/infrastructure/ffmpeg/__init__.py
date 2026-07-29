"""FFmpeg infrastructure adapters."""

from .processor import FfmpegAudioProcessor
from .recording_normalizer import FfmpegRecordingNormalizer

__all__ = ["FfmpegAudioProcessor", "FfmpegRecordingNormalizer"]
