"""WhisperX ASR, alignment, and diarization stage execution."""

import importlib
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from notekeeper.application.ports import ProgressTracker
from notekeeper.domain import ProcessingStage
from notekeeper.infrastructure.errors import InfrastructureError

from .utils import patch_speechbrain_inspect_lazy_imports

logger = logging.getLogger(__name__)


def run_asr(
    whisperx: Any,
    audio_filename: str,
    *,
    model_name: str,
    device: str,
    compute_type: str,
    batch_size: int,
    language: str | None,
    vad_method: str,
    hf_token: str | None,
    progress: ProgressTracker | None,
    patch_speechbrain: Callable[[], None] = patch_speechbrain_inspect_lazy_imports,
) -> dict[str, Any]:
    try:
        if vad_method == "pyannote":
            patch_speechbrain()
        logger.info(
            "Starting WhisperX ASR audio_path=%s model_name=%s device=%s "
            "compute_type=%s language=%s vad_method=%s hf_token_configured=%s",
            audio_filename,
            model_name,
            device,
            compute_type,
            language,
            vad_method,
            hf_token is not None,
        )
        if progress is not None:
            progress.start_stage(
                ProcessingStage.LOADING_TRANSCRIPTION_MODEL,
                timing_available=False,
            )
        model = whisperx.load_model(
            model_name,
            device,
            compute_type=compute_type,
            language=language,
            vad_method=vad_method,
            use_auth_token=hf_token,
        )
        if progress is not None:
            progress.complete_stage()
            progress.start_stage(
                ProcessingStage.TRANSCRIBING,
                timing_available=True,
            )
        result = model.transcribe(
            audio_filename,
            batch_size=batch_size,
            language=language,
            progress_callback=(
                whisperx_progress(progress) if progress is not None else None
            ),
        )
        if progress is not None:
            progress.complete_stage()
        return result
    except Exception as exc:
        logger.exception("WhisperX ASR failed for %s", audio_filename)
        raise InfrastructureError("WhisperX ASR failed") from exc


def run_alignment(
    whisperx: Any,
    transcript_result: dict[str, Any],
    audio_filename: str,
    *,
    language: str,
    device: str,
    alignment_model_name: str | None,
    alignment_model_dir: Path | None,
    alignment_model_cache_only: bool,
    progress: ProgressTracker | None,
) -> dict[str, Any]:
    try:
        logger.info(
            "Starting WhisperX alignment audio_path=%s language=%s device=%s "
            "model_name=%s model_dir=%s cache_only=%s",
            audio_filename,
            language,
            device,
            alignment_model_name,
            alignment_model_dir,
            alignment_model_cache_only,
        )
        if progress is not None:
            progress.start_stage(
                ProcessingStage.LOADING_ALIGNMENT_MODEL,
                timing_available=False,
            )
        model, metadata = whisperx.load_align_model(
            language_code=language,
            device=device,
            model_name=alignment_model_name,
            model_dir=(str(alignment_model_dir) if alignment_model_dir else None),
            model_cache_only=alignment_model_cache_only,
        )
        if progress is not None:
            progress.complete_stage()
            progress.start_stage(
                ProcessingStage.ALIGNING_TRANSCRIPT,
                timing_available=True,
            )
        result = whisperx.align(
            transcript_result.get("segments", ()),
            model,
            metadata,
            audio_filename,
            device,
            progress_callback=(
                whisperx_progress(progress) if progress is not None else None
            ),
        )
        if progress is not None:
            progress.complete_stage()
        return result
    except Exception as exc:
        logger.exception("WhisperX alignment failed for %s", audio_filename)
        raise InfrastructureError("WhisperX alignment failed") from exc


def run_diarization(
    whisperx: Any,
    transcript_result: dict[str, Any],
    audio_filename: str,
    *,
    device: str,
    diarization_model_name: str | None,
    diarization_cache_dir: Path | None,
    hf_token: str | None,
    fill_nearest: bool,
    progress: ProgressTracker | None,
    patch_speechbrain: Callable[[], None] = patch_speechbrain_inspect_lazy_imports,
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        patch_speechbrain()
        logger.info(
            "Starting WhisperX diarization audio_path=%s device=%s "
            "model_name=%s cache_dir=%s hf_token_configured=%s",
            audio_filename,
            device,
            diarization_model_name,
            diarization_cache_dir,
            hf_token is not None,
        )
        diarize = importlib.import_module("whisperx.diarize")
        if progress is not None:
            progress.start_stage(
                ProcessingStage.LOADING_DIARIZATION_MODEL,
                timing_available=False,
            )
        pipeline = diarize.DiarizationPipeline(
            model_name=diarization_model_name,
            token=hf_token,
            device=device,
            cache_dir=(str(diarization_cache_dir) if diarization_cache_dir else None),
        )
        if progress is not None:
            progress.complete_stage()
            progress.start_stage(
                ProcessingStage.DIARIZING_SPEAKERS,
                timing_available=True,
            )
        diarization_result = pipeline(
            audio_filename,
            progress_callback=(
                whisperx_progress(progress, maximum=0.99)
                if progress is not None
                else None
            ),
        )
        speaker_embeddings = None
        diarization_frame = diarization_result
        if isinstance(diarization_result, tuple):
            diarization_frame, speaker_embeddings = diarization_result

        assigned = whisperx.assign_word_speakers(
            diarization_frame,
            transcript_result,
            speaker_embeddings=speaker_embeddings,
            fill_nearest=fill_nearest,
        )
        if progress is not None:
            progress.complete_stage()
        return assigned, {
            "segments": dataframe_records(diarization_frame),
            "speaker_embeddings": speaker_embeddings,
        }
    except Exception as exc:
        logger.exception("WhisperX diarization failed for %s", audio_filename)
        raise InfrastructureError("WhisperX diarization failed") from exc


def dataframe_records(value: Any) -> Any:
    to_dict = getattr(value, "to_dict", None)
    return to_dict(orient="records") if callable(to_dict) else value


def whisperx_progress(
    progress: ProgressTracker,
    *,
    maximum: float = 1.0,
) -> Callable[[float], None]:
    def update(percent: float) -> None:
        progress.update_fraction(min(max(float(percent) / 100.0, 0.0), maximum))

    return update


__all__ = ["run_alignment", "run_asr", "run_diarization", "whisperx_progress"]
