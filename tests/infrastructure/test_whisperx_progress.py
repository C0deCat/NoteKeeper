"""WhisperX runner progress callback integration tests."""

from pathlib import Path
from types import SimpleNamespace

from notekeeper.domain import ProcessingStage
from notekeeper.infrastructure.whisperx.runner import DefaultWhisperXRunner
from notekeeper.infrastructure.whisperx import runner as runner_module


def test_runner_reports_model_and_measured_stages(monkeypatch) -> None:
    progress = RecordingProgress()
    whisperx = FakeWhisperX()
    runner = DefaultWhisperXRunner()
    monkeypatch.setattr(runner, "_import_whisperx", lambda: whisperx)
    monkeypatch.setattr(
        runner_module,
        "patch_speechbrain_inspect_lazy_imports",
        lambda: None,
    )
    import_module = runner_module.importlib.import_module
    monkeypatch.setattr(
        runner_module.importlib,
        "import_module",
        lambda name: (
            SimpleNamespace(DiarizationPipeline=FakeDiarizationPipeline)
            if name == "whisperx.diarize"
            else import_module(name)
        ),
    )

    payload = runner.run(
        Path("audio.wav"),
        model_name="tiny",
        device="cpu",
        compute_type="int8",
        batch_size=1,
        language="en",
        vad_method="silero",
        alignment_enabled=True,
        alignment_model_name=None,
        alignment_model_dir=None,
        alignment_model_cache_only=False,
        diarization_enabled=True,
        diarization_model_name=None,
        diarization_cache_dir=None,
        hf_token=None,
        fill_nearest=False,
        progress=progress,
    )

    assert payload["final"]["segments"]
    assert progress.started == [
        (ProcessingStage.LOADING_TRANSCRIPTION_MODEL, False),
        (ProcessingStage.TRANSCRIBING, True),
        (ProcessingStage.LOADING_ALIGNMENT_MODEL, False),
        (ProcessingStage.ALIGNING_TRANSCRIPT, True),
        (ProcessingStage.LOADING_DIARIZATION_MODEL, False),
        (ProcessingStage.DIARIZING_SPEAKERS, True),
    ]
    assert progress.fractions == [0.5, 1.0, 0.5, 1.0, 0.5, 0.99]
    assert progress.completed == 6


class RecordingProgress:
    def __init__(self) -> None:
        self.started: list[tuple[ProcessingStage, bool]] = []
        self.fractions: list[float] = []
        self.completed = 0

    def start_stage(
        self,
        stage: ProcessingStage,
        *,
        timing_available: bool,
    ) -> None:
        self.started.append((stage, timing_available))

    def update_fraction(self, fraction: float) -> None:
        self.fractions.append(fraction)

    def complete_stage(self) -> None:
        self.completed += 1


class FakeModel:
    def transcribe(self, _audio, **kwargs):
        kwargs["progress_callback"](50.0)
        kwargs["progress_callback"](100.0)
        return {"language": "en", "segments": [{"text": "hello"}]}


class FakeWhisperX:
    def load_model(self, *args, **kwargs):
        return FakeModel()

    def load_align_model(self, **kwargs):
        return object(), {}

    def align(self, segments, *args, **kwargs):
        kwargs["progress_callback"](50.0)
        kwargs["progress_callback"](100.0)
        return {"language": "en", "segments": list(segments)}

    def assign_word_speakers(self, _frame, transcript, **kwargs):
        return transcript


class FakeDiarizationPipeline:
    def __init__(self, **kwargs) -> None:
        pass

    def __call__(self, _audio, *, progress_callback):
        progress_callback(50.0)
        progress_callback(100.0)
        return []
