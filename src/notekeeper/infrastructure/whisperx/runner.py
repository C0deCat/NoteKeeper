"""Default WhisperX execution wrapper."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from notekeeper.infrastructure.errors import InfrastructureError

from .utils import to_json_safe


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
        alignment_enabled: bool,
        alignment_model_name: str | None,
        alignment_model_dir: Path | None,
        alignment_model_cache_only: bool,
        diarization_enabled: bool,
        diarization_model_name: str | None,
        diarization_cache_dir: Path | None,
        hf_token: str | None,
        fill_nearest: bool,
    ) -> dict[str, Any]:
        whisperx = self._import_whisperx()
        audio_filename = str(audio_path)

        asr_result = self._run_asr(
            whisperx,
            audio_filename,
            model_name=model_name,
            device=device,
            compute_type=compute_type,
            batch_size=batch_size,
            language=language,
            hf_token=hf_token,
        )
        current_result = asr_result
        alignment_result: dict[str, Any] | None = None
        diarization_payload: dict[str, Any] | None = None

        result_language = str(asr_result.get("language") or language or "").strip()
        if alignment_enabled and result_language:
            alignment_result = self._run_alignment(
                whisperx,
                current_result,
                audio_filename,
                language=result_language,
                device=device,
                alignment_model_name=alignment_model_name,
                alignment_model_dir=alignment_model_dir,
                alignment_model_cache_only=alignment_model_cache_only,
            )
            current_result = alignment_result

        if diarization_enabled:
            current_result, diarization_payload = self._run_diarization(
                whisperx,
                current_result,
                audio_filename,
                device=device,
                diarization_model_name=diarization_model_name,
                diarization_cache_dir=diarization_cache_dir,
                hf_token=hf_token,
                fill_nearest=fill_nearest,
            )

        return to_json_safe(
            {
                "asr": asr_result,
                "alignment": alignment_result,
                "diarization": diarization_payload,
                "final": current_result,
            },
        )

    def _import_whisperx(self):
        try:
            return importlib.import_module("whisperx")
        except ImportError as exc:
            raise InfrastructureError("could not import WhisperX") from exc

    def _run_asr(
        self,
        whisperx,
        audio_filename: str,
        *,
        model_name: str,
        device: str,
        compute_type: str,
        batch_size: int,
        language: str | None,
        hf_token: str | None,
    ) -> dict[str, Any]:
        try:
            model = whisperx.load_model(
                model_name,
                device,
                compute_type=compute_type,
                language=language,
                use_auth_token=hf_token,
            )
            return model.transcribe(
                audio_filename,
                batch_size=batch_size,
                language=language,
            )
        except Exception as exc:
            raise InfrastructureError("WhisperX ASR failed") from exc

    def _run_alignment(
        self,
        whisperx,
        transcript_result: dict[str, Any],
        audio_filename: str,
        *,
        language: str,
        device: str,
        alignment_model_name: str | None,
        alignment_model_dir: Path | None,
        alignment_model_cache_only: bool,
    ) -> dict[str, Any]:
        try:
            model, metadata = whisperx.load_align_model(
                language_code=language,
                device=device,
                model_name=alignment_model_name,
                model_dir=(
                    str(alignment_model_dir)
                    if alignment_model_dir is not None
                    else None
                ),
                model_cache_only=alignment_model_cache_only,
            )
            return whisperx.align(
                transcript_result.get("segments", ()),
                model,
                metadata,
                audio_filename,
                device,
            )
        except Exception as exc:
            raise InfrastructureError("WhisperX alignment failed") from exc

    def _run_diarization(
        self,
        whisperx,
        transcript_result: dict[str, Any],
        audio_filename: str,
        *,
        device: str,
        diarization_model_name: str | None,
        diarization_cache_dir: Path | None,
        hf_token: str | None,
        fill_nearest: bool,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        try:
            diarize = importlib.import_module("whisperx.diarize")
            pipeline = diarize.DiarizationPipeline(
                model_name=diarization_model_name,
                token=hf_token,
                device=device,
                cache_dir=(
                    str(diarization_cache_dir)
                    if diarization_cache_dir is not None
                    else None
                ),
            )
            diarization_result = pipeline(audio_filename)
            speaker_embeddings = None
            diarization_frame = diarization_result
            if isinstance(diarization_result, tuple):
                diarization_frame = diarization_result[0]
                speaker_embeddings = diarization_result[1]

            assigned = whisperx.assign_word_speakers(
                diarization_frame,
                transcript_result,
                speaker_embeddings=speaker_embeddings,
                fill_nearest=fill_nearest,
            )
            return assigned, {
                "segments": self._dataframe_records(diarization_frame),
                "speaker_embeddings": speaker_embeddings,
            }
        except Exception as exc:
            raise InfrastructureError("WhisperX diarization failed") from exc

    def _dataframe_records(self, value: Any) -> Any:
        to_dict = getattr(value, "to_dict", None)
        if callable(to_dict):
            return to_dict(orient="records")
        return value


__all__ = ["DefaultWhisperXRunner"]
