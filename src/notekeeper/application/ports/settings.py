"""Persistence ports for mutable settings."""

from typing import Protocol

from notekeeper.domain import UserId, UserPreferences, WorkspaceId, WorkspaceSettings


class WorkspaceSettingsRepository(Protocol):
    def get(self, workspace_id: WorkspaceId) -> WorkspaceSettings | None: ...

    def save(self, settings: WorkspaceSettings) -> None: ...

    def delete(self, workspace_id: WorkspaceId) -> None: ...


class UserPreferencesRepository(Protocol):
    def get(self, user_id: UserId) -> UserPreferences | None: ...

    def save(self, preferences: UserPreferences) -> None: ...


__all__ = ["UserPreferencesRepository", "WorkspaceSettingsRepository"]
