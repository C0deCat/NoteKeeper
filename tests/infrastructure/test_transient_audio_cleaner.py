from pathlib import Path

from notekeeper.domain import CampaignId, ProcessingJobId
from notekeeper.infrastructure.cleanup import LocalTransientAudioCleaner
from notekeeper.infrastructure.filesystem import LocalCampaignArtifactStorage


def test_transient_audio_cleaner_removes_job_audio_and_preserves_canonical_audio(
    tmp_path: Path,
) -> None:
    storage = LocalCampaignArtifactStorage(tmp_path / "artifacts")
    work_root = tmp_path / "work"
    transient = storage.path_for_uri(
        "campaign-1/records/transient/job-1/prepared.wav",
    )
    canonical = storage.path_for_uri(
        "campaign-1/records/normalized/audio-track-1.wav",
    )
    work_file = work_root / "campaign-1" / "job-1" / "audio.wav"
    for path in (transient, canonical, work_file):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"audio")
    cleaner = LocalTransientAudioCleaner(storage, work_root)

    cleaner.clean(CampaignId("campaign-1"), ProcessingJobId("job-1"))

    assert not transient.exists()
    assert not work_file.exists()
    assert canonical.is_file()


def test_transient_audio_cleaner_removes_stale_namespaces(
    tmp_path: Path,
) -> None:
    storage = LocalCampaignArtifactStorage(tmp_path / "artifacts")
    work_root = tmp_path / "work"
    transient = storage.path_for_uri(
        "campaign-1/records/transient/job-1/prepared.wav",
    )
    work_file = work_root / "campaign-1" / "job-1" / "audio.wav"
    for path in (transient, work_file):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"audio")
    cleaner = LocalTransientAudioCleaner(storage, work_root)

    cleaner.clean_stale()

    assert not transient.exists()
    assert not work_file.exists()
