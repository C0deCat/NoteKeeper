"""Default WhisperX pipeline orchestration."""

from __future__ import annotations

import gc
import importlib
import logging
from pathlib import Path
from typing import Any

from notekeeper.application.ports import ProgressTracker
from notekeeper.domain import ProcessingStage
from notekeeper.infrastructure.errors import InfrastructureError

from .stages import run_alignment, run_asr, run_diarization
from .utils import patch_speechbrain_inspect_lazy_imports, to_json_safe

logger = logging.getLogger(__name__)


class DefaultWhisperXRunner:
    def run(
        self,
        audio_path: Path,
        *,
        model_name: str,
        device: str,
        compute_type: str,
        batch_size: int,
        language: str | None,
        vad_method: str,
        alignment_enabled: bool,
        alignment_model_name: str | None,
        alignment_model_dir: Path | None,
        alignment_model_cache_only: bool,
        diarization_enabled: bool,
        diarization_model_name: str | None,
        diarization_cache_dir: Path | None,
        hf_token: str | None,
        fill_nearest: bool,
        progress: ProgressTracker | None = None,
    ) -> dict[str, Any]:
        whisperx = self._import_whisperx()
        audio_filename = str(audio_path)
        try:
            asr_result = run_asr(
                whisperx,
                audio_filename,
                model_name=model_name,
                device=device,
                compute_type=compute_type,
                batch_size=batch_size,
                language=language,
                vad_method=vad_method,
                hf_token=hf_token,
                progress=progress,
                patch_speechbrain=patch_speechbrain_inspect_lazy_imports,
            )
            current_result = asr_result
            alignment_result: dict[str, Any] | None = None
            diarization_payload: dict[str, Any] | None = None

            result_language = str(asr_result.get("language") or language or "").strip()
            if alignment_enabled and result_language:
                alignment_result = run_alignment(
                    whisperx,
                    current_result,
                    audio_filename,
                    language=result_language,
                    device=device,
                    alignment_model_name=alignment_model_name,
                    alignment_model_dir=alignment_model_dir,
                    alignment_model_cache_only=alignment_model_cache_only,
                    progress=progress,
                )
                current_result = alignment_result
            elif alignment_enabled and progress is not None:
                self._complete_inapplicable_alignment(progress)

            if diarization_enabled:
                current_result, diarization_payload = run_diarization(
                    whisperx,
                    current_result,
                    audio_filename,
                    device=device,
                    diarization_model_name=diarization_model_name,
                    diarization_cache_dir=diarization_cache_dir,
                    hf_token=hf_token,
                    fill_nearest=fill_nearest,
                    progress=progress,
                    patch_speechbrain=patch_speechbrain_inspect_lazy_imports,
                )

            return to_json_safe(
                {
                    "asr": asr_result,
                    "alignment": alignment_result,
                    "diarization": diarization_payload,
                    "final": current_result,
                }
            )
        finally:
            self._release_cuda_memory(device)

    @staticmethod
    def _import_whisperx() -> Any:
        try:
            return importlib.import_module("whisperx")
        except ImportError as exc:
            raise InfrastructureError("could not import WhisperX") from exc

    @staticmethod
    def _complete_inapplicable_alignment(progress: ProgressTracker) -> None:
        progress.start_stage(
            ProcessingStage.LOADING_ALIGNMENT_MODEL,
            timing_available=False,
        )
        progress.complete_stage()
        progress.start_stage(
            ProcessingStage.ALIGNING_TRANSCRIPT,
            timing_available=False,
        )
        progress.complete_stage()

    @staticmethod
    def _release_cuda_memory(device: str) -> None:
        if not device.lower().startswith("cuda"):
            return
        gc.collect()
        try:
            torch = importlib.import_module("torch")
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            logger.exception("Could not release cached CUDA memory")


__all__ = ["DefaultWhisperXRunner"]
