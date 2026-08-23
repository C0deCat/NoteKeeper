"""SQL helpers for explicit system and workspace repository scopes."""

import sqlite3

from notekeeper.application import RepositoryScope, SystemScope, WorkspaceScope
from notekeeper.domain import CampaignId
from notekeeper.infrastructure.errors import InfrastructureError


def workspace_predicate(
    scope: RepositoryScope,
    *,
    campaign_alias: str = "campaigns",
) -> tuple[str, tuple[str, ...]]:
    if isinstance(scope, SystemScope):
        return "1 = 1", ()
    if isinstance(scope, WorkspaceScope):
        return f"{campaign_alias}.workspace_id = ?", (str(scope.workspace_id),)
    raise TypeError(f"unsupported repository scope: {type(scope).__name__}")


def require_campaign_access(
    connection: sqlite3.Connection,
    campaign_id: CampaignId,
    scope: RepositoryScope,
) -> None:
    if isinstance(scope, SystemScope):
        return
    predicate, parameters = workspace_predicate(scope)
    row = connection.execute(
        f"SELECT 1 FROM campaigns WHERE id = ? AND {predicate}",
        (str(campaign_id), *parameters),
    ).fetchone()
    if row is None:
        raise InfrastructureError(f"campaign {campaign_id} is outside repository scope")


def require_existing_resource_access(
    connection: sqlite3.Connection,
    scope: RepositoryScope,
    *,
    table: str,
    key_column: str,
    key: str,
    campaign_join: str | None = None,
) -> None:
    """Reject an upsert that would take over an existing foreign resource id."""
    if isinstance(scope, SystemScope):
        return
    existing = connection.execute(
        f"SELECT 1 FROM {table} WHERE {key_column} = ?",
        (key,),
    ).fetchone()
    if existing is None:
        return
    join = campaign_join or (
        f"LEFT JOIN campaigns ON campaigns.id = {table}.campaign_id"
    )
    predicate, parameters = workspace_predicate(scope)
    visible = connection.execute(
        f"""
        SELECT 1 FROM {table}
        {join}
        WHERE {table}.{key_column} = ? AND {predicate}
        """,
        (key, *parameters),
    ).fetchone()
    if visible is None:
        raise InfrastructureError("resource is outside repository scope")


__all__ = [
    "require_campaign_access",
    "require_existing_resource_access",
    "workspace_predicate",
]
