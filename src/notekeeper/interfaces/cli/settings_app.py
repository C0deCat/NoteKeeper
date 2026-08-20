"""CLI commands for workspace, campaign, and user settings."""
# Typer registers nested command callbacks.
# pyright: reportUnusedFunction=false

from __future__ import annotations

import json
from pathlib import Path

import typer

from notekeeper.application import ApplicationError, SettingsService
from notekeeper.domain import WorkspaceRole
from notekeeper.infrastructure.auth import LocalCliSessionStore

from .common import RuntimeFactory, run


def create_app(runtime_factory: RuntimeFactory) -> typer.Typer:
    app = typer.Typer(help="Manage mutable settings.")
    workspace = typer.Typer(help="Workspace settings.")
    members = typer.Typer(help="Workspace access.")
    campaign = typer.Typer(help="Campaign settings.")
    user = typer.Typer(help="Current user settings.")

    @workspace.command("show")
    def show_workspace() -> None:
        runtime = runtime_factory()
        run(lambda: _echo_workspace(_service(runtime).get_workspace()))

    @workspace.command("list")
    def list_workspaces() -> None:
        runtime = runtime_factory()
        run(
            lambda: _echo_json(
                [
                    {
                        "workspace_id": str(item.id),
                        "name": item.name,
                        "owner_user_id": str(item.owner_user_id),
                    }
                    for item in _service(runtime).list_workspaces()
                ]
            )
        )

    @workspace.command("set")
    def set_workspace(
        name: str | None = typer.Option(None, "--name"),
        whisperx_model: str | None = typer.Option(None, "--whisperx-model"),
        language: str | None = typer.Option(None, "--language"),
        recap_model: str | None = typer.Option(None, "--recap-model"),
        temperature: float | None = typer.Option(None, "--temperature"),
    ) -> None:
        runtime = runtime_factory()

        def action() -> None:
            values = {
                "name": name,
                "whisperx_model_name": whisperx_model,
                "deepseek_model_name": recap_model,
                "deepseek_temperature": temperature,
            }
            kwargs = {key: value for key, value in values.items() if value is not None}
            if language is not None:
                kwargs["whisperx_language"] = None if language == "auto" else language
            if not kwargs:
                raise ValueError("at least one workspace setting option is required")
            _echo_workspace(_service(runtime).update_workspace(**kwargs))

        run(action)

    @workspace.command("reset")
    def reset_workspace(
        yes: bool = typer.Option(False, "--yes", help="Skip confirmation."),
    ) -> None:
        runtime = runtime_factory()

        def action() -> None:
            _confirm(yes, "Reset workspace processing settings?")
            _echo_workspace(_service(runtime).reset_workspace())

        run(action)

    @members.command("list")
    def list_members() -> None:
        runtime = runtime_factory()
        run(
            lambda: _echo_json(
                [
                    {
                        "user_id": str(member.user_id),
                        "login": member.login,
                        "role": member.role.value,
                    }
                    for member in _service(runtime).list_members()
                ]
            )
        )

    @members.command("add")
    def add_member(
        login: str,
        role: WorkspaceRole = typer.Option(WorkspaceRole.EDITOR, "--role"),
    ) -> None:
        runtime = runtime_factory()

        def action() -> None:
            member = _service(runtime).add_member(login, role)
            _echo_json(
                {
                    "user_id": str(member.user_id),
                    "login": member.login,
                    "role": member.role.value,
                }
            )

        run(action)

    @members.command("role")
    def set_member_role(login: str, role: WorkspaceRole) -> None:
        runtime = runtime_factory()

        def action() -> None:
            member = _service(runtime).update_member_role(login, role)
            _echo_json(
                {
                    "user_id": str(member.user_id),
                    "login": member.login,
                    "role": member.role.value,
                }
            )

        run(action)

    @members.command("remove")
    def remove_member(
        login: str,
        yes: bool = typer.Option(False, "--yes", help="Skip confirmation."),
    ) -> None:
        runtime = runtime_factory()

        def action() -> None:
            _confirm(yes, f"Remove {login!r} from this workspace?")
            _service(runtime).remove_member(login)
            _echo_json({"removed": login})

        run(action)

    @campaign.command("show")
    def show_campaign(campaign_id: str) -> None:
        runtime = runtime_factory()
        run(lambda: _echo_campaign(_service(runtime).get_campaign(campaign_id)))

    @campaign.command("set")
    def set_campaign(
        campaign_id: str,
        chunk_file: Path | None = typer.Option(None, "--chunk-file"),
        combined_file: Path | None = typer.Option(None, "--combined-file"),
    ) -> None:
        runtime = runtime_factory()

        def action() -> None:
            if chunk_file is None and combined_file is None:
                raise ValueError("at least one prompt file is required")
            result = _service(runtime).update_campaign(
                campaign_id,
                chunk_recap_prompt=_read_optional(chunk_file),
                combine_chunks_prompt=_read_optional(combined_file),
            )
            _echo_campaign(result)

        run(action)

    @campaign.command("reset")
    def reset_campaign(
        campaign_id: str,
        yes: bool = typer.Option(False, "--yes", help="Skip confirmation."),
    ) -> None:
        runtime = runtime_factory()

        def action() -> None:
            _confirm(yes, f"Reset recap prompts for campaign {campaign_id}?")
            _echo_campaign(_service(runtime).reset_campaign(campaign_id))

        run(action)

    @user.command("show")
    def show_user() -> None:
        runtime = runtime_factory()

        def action() -> None:
            settings = _service(runtime).get_user()
            _echo_json(
                {
                    "user_id": str(settings.user_id),
                    "login": settings.login,
                    "default_workspace_id": (
                        str(settings.default_workspace_id)
                        if settings.default_workspace_id is not None
                        else None
                    ),
                }
            )

        run(action)

    @user.command("login")
    def update_login(
        new_login: str,
        current_password: str | None = typer.Option(
            None, "--current-password", hide_input=True
        ),
    ) -> None:
        runtime = runtime_factory()

        def action() -> None:
            _require_auth(runtime)
            password = current_password or typer.prompt(
                "Current password", hide_input=True
            )
            updated = runtime.auth.update_login(password, new_login)
            LocalCliSessionStore(runtime.cli_auth_session_path).save(
                updated.login, password
            )
            _echo_json({"user_id": str(updated.id), "login": updated.login})

        run(action)

    @user.command("password")
    def update_password(
        current_password: str | None = typer.Option(
            None, "--current-password", hide_input=True
        ),
        new_password: str | None = typer.Option(None, "--new-password", hide_input=True),
        confirmation: str | None = typer.Option(
            None, "--new-password-confirmation", hide_input=True
        ),
    ) -> None:
        runtime = runtime_factory()

        def action() -> None:
            _require_auth(runtime)
            current = current_password or typer.prompt(
                "Current password", hide_input=True
            )
            new = new_password or typer.prompt("New password", hide_input=True)
            confirmed = confirmation or typer.prompt(
                "Repeat new password", hide_input=True
            )
            if new != confirmed:
                raise ApplicationError("passwords do not match")
            updated = runtime.auth.update_password(current, new)
            LocalCliSessionStore(runtime.cli_auth_session_path).save(updated.login, new)
            _echo_json({"user_id": str(updated.id), "login": updated.login})

        run(action)

    @user.command("default-workspace")
    def default_workspace(workspace_id: str) -> None:
        runtime = runtime_factory()

        def action() -> None:
            settings = _service(runtime).update_default_workspace(workspace_id)
            _echo_json(
                {
                    "user_id": str(settings.user_id),
                    "login": settings.login,
                    "default_workspace_id": str(settings.default_workspace_id),
                }
            )

        run(action)

    workspace.add_typer(members, name="members")
    app.add_typer(workspace, name="workspace")
    app.add_typer(campaign, name="campaign")
    app.add_typer(user, name="user")
    return app


def _service(runtime) -> SettingsService:
    service = runtime.use_cases.settings
    if service is None:
        raise ApplicationError("settings service is unavailable")
    return service


def _require_auth(runtime) -> None:
    if not runtime.auth.enabled:
        raise ApplicationError("authentication is disabled")


def _confirm(skip: bool, message: str) -> None:
    if not skip and not typer.confirm(message):
        raise ApplicationError("operation canceled")


def _read_optional(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"could not read prompt file: {path}") from exc


def _echo_workspace(settings) -> None:
    _echo_json(
        {
            "workspace_id": str(settings.workspace_id),
            "name": settings.name,
            "whisperx_model_name": settings.whisperx_model_name,
            "whisperx_language": settings.whisperx_language or "auto",
            "deepseek_model_name": settings.deepseek_model_name,
            "deepseek_temperature": settings.deepseek_temperature,
            "inherited": settings.inherited,
        }
    )


def _echo_campaign(settings) -> None:
    _echo_json(
        {
            "campaign_id": str(settings.campaign_id),
            "chunk_recap_prompt": settings.chunk_recap_prompt,
            "combine_chunks_prompt": settings.combine_chunks_prompt,
        }
    )


def _echo_json(payload) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


__all__ = ["create_app"]
