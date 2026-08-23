"""Serialization helpers for immutable processing settings snapshots."""

from typing import Any

from notekeeper.domain import ProcessingSettingsSnapshot


def processing_settings_to_dict(
    snapshot: ProcessingSettingsSnapshot,
) -> dict[str, Any]:
    return {
        "schema_version": snapshot.schema_version,
        "whisperx_model_name": snapshot.whisperx_model_name,
        "whisperx_language": snapshot.whisperx_language,
        "deepseek_model_name": snapshot.deepseek_model_name,
        "deepseek_temperature": snapshot.deepseek_temperature,
        "chunk_recap_prompt": snapshot.chunk_recap_prompt,
        "combine_chunks_prompt": snapshot.combine_chunks_prompt,
    }


def processing_settings_from_dict(
    payload: dict[str, Any],
) -> ProcessingSettingsSnapshot:
    return ProcessingSettingsSnapshot(
        schema_version=int(payload.get("schema_version", 1)),
        whisperx_model_name=str(payload["whisperx_model_name"]),
        whisperx_language=(
            str(payload["whisperx_language"])
            if payload.get("whisperx_language") is not None
            else None
        ),
        deepseek_model_name=str(payload["deepseek_model_name"]),
        deepseek_temperature=float(payload["deepseek_temperature"]),
        chunk_recap_prompt=str(payload["chunk_recap_prompt"]),
        combine_chunks_prompt=str(payload["combine_chunks_prompt"]),
    )


__all__ = ["processing_settings_from_dict", "processing_settings_to_dict"]
