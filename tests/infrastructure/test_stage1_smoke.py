from __future__ import annotations

import subprocess
import wave
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from typing import Any

from notekeeper.application import (
    RunProcessingJob,
    RunProcessingJobCommand,
    SubmitRecordingForProcessing,
    SubmitRecordingForProcessingCommand,
)
from notekeeper.domain import (
    ArtifactRef,
    Campaign,
    CampaignId,
    JobStatus,
    Participant,
    ParticipantId,
    SpeakerLabel,
    SpeakerMappingSource,
    VoiceSample,
    VoiceSampleId,
)
from notekeeper.infrastructure.deepseek import DeepSeekRecapGenerator
from notekeeper.infrastructure.deepseek.interfaces import DeepSeekChatCompletion
from notekeeper.infrastructure.ffmpeg import FfmpegAudioProcessor
from notekeeper.infrastructure.filesystem import (
    LocalAudioMetadataReader,
    LocalCampaignArtifactStorage,
    LocalPreparedAudioManifestStore,
)
from notekeeper.infrastructure.speaker_mapping import SampleBasedSpeakerIdentifier
from notekeeper.infrastructure.sqlite import (
    SQLiteAudioTrackRepository,
    SQLiteCampaignRepository,
    SQLiteDatabase,
    SQLiteJobRepository,
    SQLiteRecapRepository,
    SQLiteSpeakerMappingRepository,
    SQLiteTranscriptRepository,
)
from notekeeper.infrastructure.tokenization import TiktokenTranscriptTokenizer
from notekeeper.infrastructure.whisperx import (
    LocalWhisperXPayloadStore,
    WhisperXTranscriber,
)


class FakeWhisperXRunner:
    def run(self, audio_path: Path, **kwargs: Any) -> dict[str, Any]:
        return {
            "asr": {"segments": []},
            "alignment": None,
            "diarization": {"segments": []},
            "final": {
                "segments": [
                    {
                        "start": 0.0,
                        "end": 0.8,
                        "speaker": "SPEAKER_00",
                        "text": "We enter the crypt.",
                    },
                    {
                        "start": 1.1,
                        "end": 1.8,
                        "speaker": "SPEAKER_00",
                        "text": "Alice sample phrase.",
                    },
                ],
            },
        }


class FakeDeepSeekClient:
    def __init__(self) -> None:
        self.calls: list[tuple[dict[str, str], ...]] = []
        self.responses = [
            "## Chunk Recap\nThe party enters the crypt.",
            "# Session Recap\nDone.",
        ]

    def complete(
        self,
        *,
        model: str,
        messages: tuple[dict[str, str], ...],
        temperature: float,
        timeout_seconds: float,
    ) -> DeepSeekChatCompletion:
        self.calls.append(messages)
        return DeepSeekChatCompletion(text=self.responses.pop(0))


class FixedClock:
    def __init__(self) -> None:
        self._now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        current = self._now
        self._now += timedelta(seconds=1)
        return current


class FixedIds:
    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def campaign_id(self) -> str:
        return self._next("campaign")

    def participant_id(self) -> str:
        return self._next("participant")

    def voice_sample_id(self) -> str:
        return self._next("voice-sample")

    def audio_track_id(self) -> str:
        return self._next("audio-track")

    def processing_job_id(self) -> str:
        return self._next("job")

    def transcript_id(self) -> str:
        return self._next("transcript")

    def recap_id(self) -> str:
        return self._next("recap")

    def _next(self, prefix: str) -> str:
        self._counts[prefix] = self._counts.get(prefix, 0) + 1
        return f"{prefix}-{self._counts[prefix]}"


def test_stage1_processing_smoke_with_fake_external_boundaries(
    tmp_path: Path,
    monkeypatch,
) -> None:
    storage = LocalCampaignArtifactStorage(tmp_path / "artifacts")
    database = SQLiteDatabase(tmp_path / "notekeeper.sqlite3")
    database.initialize()
    campaigns = SQLiteCampaignRepository(database)
    audio_tracks = SQLiteAudioTrackRepository(database)
    transcripts = SQLiteTranscriptRepository(database, storage)
    recaps = SQLiteRecapRepository(database, storage)
    jobs = SQLiteJobRepository(database)
    speaker_mappings = SQLiteSpeakerMappingRepository(database)
    manifest_store = LocalPreparedAudioManifestStore(storage)
    storage.ensure_campaign_layout(CampaignId("campaign-1"))
    sample_uri = "campaign-1/players/Alice/sample.wav"
    session_uri = "campaign-1/records/session.wav"
    _write_wav(storage.path_for_uri(sample_uri), duration_seconds=1.0)
    _write_wav(storage.path_for_uri(session_uri), duration_seconds=1.0)
    metadata_reader = LocalAudioMetadataReader(storage, ffprobe_path="missing-ffprobe")
    sample_artifact = ArtifactRef(uri=sample_uri)
    sample_metadata = metadata_reader.read(sample_artifact)
    campaigns.save(
        Campaign(
            id=CampaignId("campaign-1"),
            name="Smoke",
            participants=(
                Participant(
                    id=ParticipantId("participant-1"),
                    campaign_id=CampaignId("campaign-1"),
                    display_name="Alice",
                ),
            ),
            voice_samples=(
                VoiceSample(
                    id=VoiceSampleId("sample-1"),
                    campaign_id=CampaignId("campaign-1"),
                    participant_id=ParticipantId("participant-1"),
                    artifact=sample_artifact,
                    metadata=sample_metadata,
                ),
            ),
        ),
    )

    def fake_subprocess_run(command, check, capture_output, text, **kwargs):
        if command[0] == "missing-ffprobe":
            raise FileNotFoundError(command[0])

        _write_wav(Path(command[-1]), duration_seconds=1.0)
        return subprocess.CompletedProcess(command, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_subprocess_run)

    class FakeFfmpegProcess:
        stdout = StringIO("progress=end\n")
        stderr = StringIO("")

        def wait(self) -> int:
            return 0

    def fake_subprocess_popen(command, **kwargs):
        _write_wav(Path(command[-1]), duration_seconds=1.0)
        return FakeFfmpegProcess()

    monkeypatch.setattr(subprocess, "Popen", fake_subprocess_popen)
    clock = FixedClock()
    ids = FixedIds()
    submit = SubmitRecordingForProcessing(
        campaigns,
        audio_tracks,
        jobs,
        metadata_reader,
        clock,
        ids,
    )
    deepseek_client = FakeDeepSeekClient()
    run = RunProcessingJob(
        campaigns,
        audio_tracks,
        transcripts,
        recaps,
        jobs,
        FfmpegAudioProcessor(
            storage,
            manifest_store,
            ffmpeg_path="fake-ffmpeg",
            processing_work_root=tmp_path / "work",
            now=clock.now,
        ),
        WhisperXTranscriber(
            storage,
            LocalWhisperXPayloadStore(storage),
            runner=FakeWhisperXRunner(),
            alignment_enabled=False,
            diarization_enabled=False,
            now=clock.now,
        ),
        SampleBasedSpeakerIdentifier(),
        speaker_mappings,
        TiktokenTranscriptTokenizer(max_token_count=500),
        DeepSeekRecapGenerator(
            chunk_recap_prompt="chunk prompt",
            combine_chunks_prompt="combine prompt",
            model_name="test-model",
            api_key=None,
            retry_count=0,
            client=deepseek_client,
        ),
        clock,
        ids,
    )

    submitted = submit.execute(
        SubmitRecordingForProcessingCommand(
            campaign_id="campaign-1",
            artifact_uri=session_uri,
        ),
    )
    result = run.execute(RunProcessingJobCommand(job_id=submitted.job.id))

    assert result.job.status is JobStatus.COMPLETED
    assert result.transcript is not None
    assert result.recap is not None
    assert result.transcript.segments[0].speaker_label == SpeakerLabel.named("Alice")
    assert jobs.get(result.job.id) == result.job
    assert transcripts.get(result.transcript.id) == result.transcript
    assert recaps.get(result.recap.id) == result.recap
    mappings = speaker_mappings.list_for_job(result.job.id)
    assert len(mappings) == 1
    assert mappings[0].mapping.source is SpeakerMappingSource.SAMPLE_BASED
    assert manifest_store.read_for_job(
        campaign_id=CampaignId("campaign-1"),
        job_id=result.job.id,
    )["prepared_artifact"]["uri"] == "campaign-1/records/prepared/job-1/prepared.wav"
    assert storage.path_for_uri(
        "campaign-1/transcripts/raw-whisperx/transcript-1.json",
    ).is_file()
    assert storage.path_for_uri("campaign-1/recaps/recap-1.json").is_file()
    assert len(deepseek_client.calls) == 2


def _write_wav(path: Path, *, duration_seconds: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame_rate = 16000
    frame_count = int(frame_rate * duration_seconds)
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(frame_rate)
        audio.writeframes(b"\x00\x00" * frame_count)
