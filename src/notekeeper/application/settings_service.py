"""Application service for mutable settings and workspace access."""

from __future__ import annotations

from dataclasses import replace

from notekeeper.domain import (
    AuthenticatedUser,
    CampaignId,
    CampaignSettings,
    ProcessingSettingsSnapshot,
    SettingsCatalog,
    UserPreferences,
    UserSettings,
    Workspace,
    WorkspaceId,
    WorkspaceMemberSettings,
    WorkspaceMembership,
    WorkspaceRole,
    WorkspaceSettings,
)

from .access_context import AccessContext
from .authenticator import Authenticator
from .errors import AuthorizationError, InvalidOperationError, NotFoundError
from .ports import (
    CampaignRepository,
    RecapGuidances,
    UserPreferencesRepository,
    WorkspaceRepository,
    WorkspaceSettingsRepository,
)


class SettingsService:
    def __init__(
        self,
        access: AccessContext,
        workspace_repository: WorkspaceRepository,
        workspace_settings_repository: WorkspaceSettingsRepository,
        user_preferences_repository: UserPreferencesRepository,
        campaign_repository: CampaignRepository,
        recap_guidances: RecapGuidances,
        authenticator: Authenticator,
        catalog: SettingsCatalog,
        *,
        default_whisperx_model_name: str,
        default_whisperx_language: str | None,
        default_deepseek_model_name: str,
        default_deepseek_temperature: float,
    ) -> None:
        self._access = access
        self._workspaces = workspace_repository
        self._workspace_settings = workspace_settings_repository
        self._preferences = user_preferences_repository
        self._campaigns = campaign_repository
        self._recap_guidances = recap_guidances
        self._authenticator = authenticator
        self._catalog = catalog
        self._default_whisperx_model_name = default_whisperx_model_name
        self._default_whisperx_language = default_whisperx_language
        self._default_deepseek_model_name = default_deepseek_model_name
        self._default_deepseek_temperature = default_deepseek_temperature

    @property
    def catalog(self) -> SettingsCatalog:
        return self._catalog

    def get_workspace(self) -> WorkspaceSettings:
        self._require_membership()
        workspace = self._workspaces.get(self._access.workspace_id)
        if workspace is None:
            raise NotFoundError(f"workspace {self._access.workspace_id} was not found")
        override = self._workspace_settings.get(workspace.id)
        if override is not None:
            return replace(override, name=workspace.name, inherited=False)
        return WorkspaceSettings(
            workspace_id=workspace.id,
            name=workspace.name,
            whisperx_model_name=self._default_whisperx_model_name,
            whisperx_language=self._default_whisperx_language,
            deepseek_model_name=self._default_deepseek_model_name,
            deepseek_temperature=self._default_deepseek_temperature,
            inherited=True,
        )

    def update_workspace(
        self,
        *,
        name: str | None = None,
        whisperx_model_name: str | None = None,
        whisperx_language: str | None | object = ...,
        deepseek_model_name: str | None = None,
        deepseek_temperature: float | None = None,
    ) -> WorkspaceSettings:
        self._require_owner()
        current = self.get_workspace()
        language = (
            current.whisperx_language
            if whisperx_language is ...
            else whisperx_language
        )
        if language is not None and not isinstance(language, str):
            raise ValueError("whisperx_language must be text or None")
        updated = WorkspaceSettings(
            workspace_id=current.workspace_id,
            name=name if name is not None else current.name,
            whisperx_model_name=(
                whisperx_model_name
                if whisperx_model_name is not None
                else current.whisperx_model_name
            ),
            whisperx_language=language,
            deepseek_model_name=(
                deepseek_model_name
                if deepseek_model_name is not None
                else current.deepseek_model_name
            ),
            deepseek_temperature=(
                deepseek_temperature
                if deepseek_temperature is not None
                else current.deepseek_temperature
            ),
        )
        self._validate_workspace_settings(updated)
        workspace = self._workspaces.get(updated.workspace_id)
        if workspace is None:
            raise NotFoundError(f"workspace {updated.workspace_id} was not found")
        if workspace.name != updated.name:
            self._workspaces.save(replace(workspace, name=updated.name))
        self._workspace_settings.save(updated)
        return updated

    def reset_workspace(self) -> WorkspaceSettings:
        self._require_owner()
        self._workspace_settings.delete(self._access.workspace_id)
        return self.get_workspace()

    def list_workspaces(self) -> tuple[Workspace, ...]:
        return self._workspaces.list_for_user(self._access.actor_user_id)

    def current_role(self) -> WorkspaceRole:
        return self._require_membership().role

    def list_members(self) -> tuple[WorkspaceMemberSettings, ...]:
        self._require_membership()
        members: list[WorkspaceMemberSettings] = []
        for membership in self._workspaces.list_members(self._access.workspace_id):
            user = self._authenticator.get(membership.user_id)
            members.append(
                WorkspaceMemberSettings(
                    user_id=membership.user_id,
                    login=user.login if user is not None else str(membership.user_id),
                    role=membership.role,
                )
            )
        return tuple(members)

    def add_member(self, login: str, role: WorkspaceRole) -> WorkspaceMemberSettings:
        self._require_owner()
        self._require_assignable_role(role)
        user = self._authenticator.find_by_login(login)
        if user is None:
            raise NotFoundError(f"user login {login!r} was not found")
        if self._workspaces.membership(self._access.workspace_id, user.id) is not None:
            raise InvalidOperationError(f"user {user.login!r} is already a member")
        self._workspaces.save_member(
            WorkspaceMembership(self._access.workspace_id, user.id, role)
        )
        return WorkspaceMemberSettings(user.id, user.login, role)

    def update_member_role(
        self, login: str, role: WorkspaceRole
    ) -> WorkspaceMemberSettings:
        self._require_owner()
        self._require_assignable_role(role)
        user = self._authenticator.find_by_login(login)
        if user is None:
            raise NotFoundError(f"user login {login!r} was not found")
        membership = self._workspaces.membership(self._access.workspace_id, user.id)
        if membership is None:
            raise NotFoundError(f"user {user.login!r} is not a workspace member")
        if membership.role is WorkspaceRole.OWNER:
            raise InvalidOperationError("workspace owner role cannot be changed")
        self._workspaces.save_member(replace(membership, role=role))
        return WorkspaceMemberSettings(user.id, user.login, role)

    def remove_member(self, login: str) -> None:
        self._require_owner()
        user = self._authenticator.find_by_login(login)
        if user is None:
            raise NotFoundError(f"user login {login!r} was not found")
        membership = self._workspaces.membership(self._access.workspace_id, user.id)
        if membership is None:
            raise NotFoundError(f"user {user.login!r} is not a workspace member")
        if membership.role is WorkspaceRole.OWNER:
            raise InvalidOperationError("workspace owner cannot be removed")
        self._workspaces.delete_member(self._access.workspace_id, user.id)

    def get_campaign(self, campaign_id: str) -> CampaignSettings:
        self._require_membership()
        campaign = self._campaigns.get(CampaignId(campaign_id))
        if campaign is None:
            raise NotFoundError(f"campaign {campaign_id} was not found")
        return CampaignSettings(
            campaign_id=campaign.id,
            chunk_recap_prompt=(
                self._recap_guidances.get_chunk_recap_guidances(campaign.id)
            ),
            combine_chunks_prompt=(
                self._recap_guidances.get_combined_recap_guidances(campaign.id)
            ),
        )

    def update_campaign(
        self,
        campaign_id: str,
        *,
        chunk_recap_prompt: str | None = None,
        combine_chunks_prompt: str | None = None,
    ) -> CampaignSettings:
        self._require_editor()
        current = self.get_campaign(campaign_id)
        updated = CampaignSettings(
            current.campaign_id,
            (
                chunk_recap_prompt
                if chunk_recap_prompt is not None
                else current.chunk_recap_prompt
            ),
            (
                combine_chunks_prompt
                if combine_chunks_prompt is not None
                else current.combine_chunks_prompt
            ),
        )
        self._recap_guidances.save_recap_guidances(
            updated.campaign_id,
            chunk_recap_guidances=updated.chunk_recap_prompt,
            combined_recap_guidances=updated.combine_chunks_prompt,
        )
        return updated

    def reset_campaign(self, campaign_id: str) -> CampaignSettings:
        self._require_editor()
        current = self.get_campaign(campaign_id)
        self._recap_guidances.reset_recap_guidances(current.campaign_id)
        return self.get_campaign(campaign_id)

    def snapshot_for_campaign(self, campaign_id: str) -> ProcessingSettingsSnapshot:
        workspace = self.get_workspace()
        self._validate_workspace_settings(workspace)
        campaign = self.get_campaign(campaign_id)
        return ProcessingSettingsSnapshot(
            whisperx_model_name=workspace.whisperx_model_name,
            whisperx_language=workspace.whisperx_language,
            deepseek_model_name=workspace.deepseek_model_name,
            deepseek_temperature=workspace.deepseek_temperature,
            chunk_recap_prompt=campaign.chunk_recap_prompt,
            combine_chunks_prompt=campaign.combine_chunks_prompt,
        )

    def get_user(self) -> UserSettings:
        user = self._authenticator.get(self._access.actor_user_id)
        if user is None:
            raise NotFoundError(f"user {self._access.actor_user_id} was not found")
        preferences = self._preferences.get(user.id)
        return UserSettings(
            user.id,
            user.login,
            preferences.default_workspace_id if preferences is not None else None,
        )

    def update_default_workspace(self, workspace_id: str) -> UserSettings:
        target = WorkspaceId(workspace_id)
        if self._workspaces.membership(target, self._access.actor_user_id) is None:
            raise NotFoundError(f"workspace {target} was not found")
        self._preferences.save(UserPreferences(self._access.actor_user_id, target))
        return self.get_user()

    def update_login(
        self,
        current_password: str,
        new_login: str,
    ) -> AuthenticatedUser:
        return self._authenticator.update_login(
            self._access.actor_user_id,
            current_password,
            new_login,
        )

    def update_password(
        self,
        current_password: str,
        new_password: str,
    ) -> AuthenticatedUser:
        return self._authenticator.update_password(
            self._access.actor_user_id,
            current_password,
            new_password,
        )

    def _validate_workspace_settings(self, settings: WorkspaceSettings) -> None:
        if settings.whisperx_model_name not in self._catalog.whisperx_models:
            raise ValueError("whisperx model is not allowed by the platform")
        language = settings.whisperx_language or "auto"
        if language not in self._catalog.whisperx_languages:
            raise ValueError("whisperx language is not allowed by the platform")
        if settings.deepseek_model_name not in self._catalog.deepseek_models:
            raise ValueError("DeepSeek model is not allowed by the platform")
        if settings.deepseek_temperature not in self._catalog.temperatures:
            raise ValueError("DeepSeek temperature is not allowed by the platform")

    def _require_membership(self) -> WorkspaceMembership:
        membership = self._workspaces.membership(
            self._access.workspace_id,
            self._access.actor_user_id,
        )
        if membership is None:
            raise AuthorizationError("workspace access has been revoked")
        return membership

    def _require_owner(self) -> None:
        if self._require_membership().role is not WorkspaceRole.OWNER:
            raise AuthorizationError("workspace owner role is required")

    def _require_editor(self) -> None:
        if self._require_membership().role is WorkspaceRole.VIEWER:
            raise AuthorizationError("workspace editor role is required")

    @staticmethod
    def _require_assignable_role(role: WorkspaceRole) -> None:
        if role not in {WorkspaceRole.EDITOR, WorkspaceRole.VIEWER}:
            raise InvalidOperationError("only editor or viewer roles can be assigned")


__all__ = ["SettingsService"]
