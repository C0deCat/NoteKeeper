"""Campaign synchronization action for the Textual interface."""

from __future__ import annotations

from typing import TYPE_CHECKING

from notekeeper.application import SyncCampaignFolderCommand

if TYPE_CHECKING:
    from .tui import NoteKeeperTui


def sync_campaign_folder(app: NoteKeeperTui, campaign_id: str) -> None:
    app.run_worker(
        lambda: app.runtime.use_cases.sync_campaign_folder.execute(
            SyncCampaignFolderCommand(campaign_id=campaign_id),
        ),
        group="sync",
        thread=True,
        exit_on_error=False,
    )
