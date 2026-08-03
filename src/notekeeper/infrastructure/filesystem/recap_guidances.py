"""Campaign-specific recap guidance storage backed by JSON files."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from notekeeper.application.ports import RecapGuidances
from notekeeper.domain import CampaignId

from ..errors import InfrastructureError
from .storage import LocalCampaignArtifactStorage


CHUNK_RECAP_PROMPT_KEY = "chunk_recap_prompt"
COMBINE_CHUNKS_PROMPT_KEY = "combine_chunks_prompt"
RECAP_PROMPTS_FILE_NAME = "recap_prompts.json"
DEFAULT_RECAP_PROMPTS_TEMPLATE = Path("data") / RECAP_PROMPTS_FILE_NAME


class JsonCampaignRecapGuidances(RecapGuidances):
    def __init__(
        self,
        storage: LocalCampaignArtifactStorage,
        template_path: str | Path = DEFAULT_RECAP_PROMPTS_TEMPLATE,
    ) -> None:
        self._storage = storage
        self._template_path = Path(template_path)

    def get_chunk_recap_guidances(self, campaign_id: CampaignId) -> str:
        return self._load_campaign_payload(campaign_id)[CHUNK_RECAP_PROMPT_KEY]

    def get_combined_recap_guidances(self, campaign_id: CampaignId) -> str:
        return self._load_campaign_payload(campaign_id)[COMBINE_CHUNKS_PROMPT_KEY]

    def save_recap_guidances(
        self,
        campaign_id: CampaignId,
        *,
        chunk_recap_guidances: str,
        combined_recap_guidances: str,
    ) -> None:
        path = self._campaign_file(campaign_id)
        self._load_campaign_payload(campaign_id)
        payload = {
            CHUNK_RECAP_PROMPT_KEY: self._required_prompt(
                chunk_recap_guidances,
                CHUNK_RECAP_PROMPT_KEY,
                path,
            ),
            COMBINE_CHUNKS_PROMPT_KEY: self._required_prompt(
                combined_recap_guidances,
                COMBINE_CHUNKS_PROMPT_KEY,
                path,
            ),
        }
        self._write_payload(path, payload)

    def _load_campaign_payload(self, campaign_id: CampaignId) -> dict[str, str]:
        path = self._campaign_file(campaign_id)
        if path.is_symlink():
            raise InfrastructureError(
                f"recap prompts file must not be a symbolic link: {path}",
            )
        if not path.exists():
            template = self._read_payload(self._template_path, source="template")
            self._storage.ensure_campaign_layout(campaign_id)
            self._write_payload(path, template)
        elif not path.is_file():
            raise InfrastructureError(f"recap prompts path is not a file: {path}")
        return self._read_payload(path, source="campaign")

    def _campaign_file(self, campaign_id: CampaignId) -> Path:
        return self._storage.campaign_path(campaign_id) / RECAP_PROMPTS_FILE_NAME

    def _read_payload(self, path: Path, *, source: str) -> dict[str, str]:
        if path.is_symlink():
            raise InfrastructureError(
                f"recap prompts {source} must not be a symbolic link: {path}",
            )
        if not path.is_file():
            raise InfrastructureError(f"recap prompts {source} does not exist: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise InfrastructureError(
                f"could not read recap prompts {source}: {path}",
            ) from exc
        if not isinstance(payload, dict):
            raise InfrastructureError(
                f"recap prompts {source} must contain a JSON object: {path}",
            )
        return {
            CHUNK_RECAP_PROMPT_KEY: self._required_payload_prompt(
                payload,
                CHUNK_RECAP_PROMPT_KEY,
                path,
                source,
            ),
            COMBINE_CHUNKS_PROMPT_KEY: self._required_payload_prompt(
                payload,
                COMBINE_CHUNKS_PROMPT_KEY,
                path,
                source,
            ),
        }

    def _required_payload_prompt(
        self,
        payload: dict[str, Any],
        key: str,
        path: Path,
        source: str,
    ) -> str:
        return self._required_prompt(payload.get(key), key, path, source=source)

    def _required_prompt(
        self,
        value: object,
        key: str,
        path: Path,
        *,
        source: str = "campaign",
    ) -> str:
        if not isinstance(value, str) or not value.strip():
            raise InfrastructureError(
                f"recap prompts {source} is missing prompt {key}: {path}",
            )
        return value

    def _write_payload(self, path: Path, payload: dict[str, str]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            file_descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{path.name}.",
                suffix=".tmp",
                dir=path.parent,
            )
            temporary_path = Path(temporary_name)
            with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
            temporary_path = None
        except OSError as exc:
            raise InfrastructureError(
                f"could not write recap prompts file: {path}",
            ) from exc
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass


__all__ = ["JsonCampaignRecapGuidances"]
