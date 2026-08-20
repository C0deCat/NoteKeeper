"""Workspace, campaign, user, and processing settings DTOs."""

from __future__ import annotations

from dataclasses import dataclass

from ..enums import WorkspaceRole
from ..ids import CampaignId, UserId, WorkspaceId
from ..validation import non_empty_str


def _validated_temperature(value: float) -> float:
    value = float(value)
    if not 0.0 <= value <= 2.0:
        raise ValueError("deepseek_temperature must be between 0.0 and 2.0")
    if abs(value * 10 - round(value * 10)) > 1e-9:
        raise ValueError("deepseek_temperature must use increments of 0.1")
    return value


@dataclass(frozen=True, slots=True)
class WorkspaceSettings:
    workspace_id: WorkspaceId
    name: str
    whisperx_model_name: str
    whisperx_language: str | None
    deepseek_model_name: str
    deepseek_temperature: float
    inherited: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", non_empty_str(self.name, "name"))
        object.__setattr__(
            self,
            "whisperx_model_name",
            non_empty_str(self.whisperx_model_name, "whisperx_model_name"),
        )
        if self.whisperx_language is not None:
            object.__setattr__(
                self,
                "whisperx_language",
                non_empty_str(self.whisperx_language, "whisperx_language"),
            )
        object.__setattr__(
            self,
            "deepseek_model_name",
            non_empty_str(self.deepseek_model_name, "deepseek_model_name"),
        )
        object.__setattr__(
            self,
            "deepseek_temperature",
            _validated_temperature(self.deepseek_temperature),
        )


@dataclass(frozen=True, slots=True)
class CampaignSettings:
    campaign_id: CampaignId
    chunk_recap_prompt: str
    combine_chunks_prompt: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "chunk_recap_prompt",
            non_empty_str(self.chunk_recap_prompt, "chunk_recap_prompt"),
        )
        object.__setattr__(
            self,
            "combine_chunks_prompt",
            non_empty_str(self.combine_chunks_prompt, "combine_chunks_prompt"),
        )


@dataclass(frozen=True, slots=True)
class UserPreferences:
    user_id: UserId
    default_workspace_id: WorkspaceId | None = None


@dataclass(frozen=True, slots=True)
class UserSettings:
    user_id: UserId
    login: str
    default_workspace_id: WorkspaceId | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "login", non_empty_str(self.login, "login"))


@dataclass(frozen=True, slots=True)
class WorkspaceMemberSettings:
    user_id: UserId
    login: str
    role: WorkspaceRole

    def __post_init__(self) -> None:
        object.__setattr__(self, "login", non_empty_str(self.login, "login"))


@dataclass(frozen=True, slots=True)
class SettingsCatalog:
    whisperx_models: tuple[str, ...]
    whisperx_languages: tuple[str, ...]
    deepseek_models: tuple[str, ...]
    temperatures: tuple[float, ...] = tuple(index / 10 for index in range(21))

    def __post_init__(self) -> None:
        for field in ("whisperx_models", "whisperx_languages", "deepseek_models"):
            values = tuple(non_empty_str(value, field) for value in getattr(self, field))
            if not values or len(set(values)) != len(values):
                raise ValueError(f"{field} must contain unique non-empty values")
            object.__setattr__(self, field, values)
        temperatures = tuple(_validated_temperature(value) for value in self.temperatures)
        if not temperatures or len(set(temperatures)) != len(temperatures):
            raise ValueError("temperatures must contain unique values")
        object.__setattr__(self, "temperatures", temperatures)


@dataclass(frozen=True, slots=True)
class ProcessingSettingsSnapshot:
    whisperx_model_name: str
    whisperx_language: str | None
    deepseek_model_name: str
    deepseek_temperature: float
    chunk_recap_prompt: str
    combine_chunks_prompt: str
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported processing settings snapshot version")
        object.__setattr__(
            self,
            "whisperx_model_name",
            non_empty_str(self.whisperx_model_name, "whisperx_model_name"),
        )
        if self.whisperx_language is not None:
            object.__setattr__(
                self,
                "whisperx_language",
                non_empty_str(self.whisperx_language, "whisperx_language"),
            )
        object.__setattr__(
            self,
            "deepseek_model_name",
            non_empty_str(self.deepseek_model_name, "deepseek_model_name"),
        )
        object.__setattr__(
            self,
            "deepseek_temperature",
            _validated_temperature(self.deepseek_temperature),
        )
        object.__setattr__(
            self,
            "chunk_recap_prompt",
            non_empty_str(self.chunk_recap_prompt, "chunk_recap_prompt"),
        )
        object.__setattr__(
            self,
            "combine_chunks_prompt",
            non_empty_str(self.combine_chunks_prompt, "combine_chunks_prompt"),
        )


__all__ = [
    "CampaignSettings",
    "ProcessingSettingsSnapshot",
    "SettingsCatalog",
    "UserPreferences",
    "UserSettings",
    "WorkspaceMemberSettings",
    "WorkspaceSettings",
]
