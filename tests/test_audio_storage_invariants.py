from inspect import Parameter, signature
from pathlib import Path

from notekeeper.application import (
    RegisterAudioTrack,
    SubmitRecordingForProcessing,
    SyncCampaignFolder,
    UpdateAudioTrack,
)
from notekeeper.application.ports import AudioRecordingNormalizer


def test_audio_ingestion_dependencies_are_required() -> None:
    for use_case in (
        RegisterAudioTrack,
        SubmitRecordingForProcessing,
        SyncCampaignFolder,
        UpdateAudioTrack,
    ):
        parameters = signature(use_case.__init__).parameters
        assert parameters["audio_normalizer"].default is Parameter.empty
        assert parameters["artifact_storage"].default is Parameter.empty


def test_removed_audio_layout_and_compatibility_tokens_are_absent() -> None:
    project_root = Path(__file__).resolve().parents[1]
    forbidden_tokens = (
        "records/" + "prepared",
        "transient-" + "v2",
        "prepared_audio_" + "sample_rate_hz",
        "prepared_audio_" + "channels",
        "prepared_audio_" + "codec",
        "prepared_audio_" + "container",
        "AudioRecordingNormalizer " + "| None",
    )
    violations: list[str] = []

    for source_root in (project_root / "src", project_root / "tests"):
        for path in source_root.rglob("*.py"):
            if path == Path(__file__).resolve():
                continue
            content = path.read_text(encoding="utf-8")
            for token in forbidden_tokens:
                if token in content:
                    violations.append(f"{path.relative_to(project_root)}: {token}")

    assert violations == []
    assert not hasattr(AudioRecordingNormalizer, "is_" + "canonical")
