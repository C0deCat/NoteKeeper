"""Campaign synchronization action for the Textual interface."""

from notekeeper.application import SyncCampaignFolderCommand


def sync_campaign_folder(app, campaign_id: str) -> None:
    app.run_worker(
        lambda: app.runtime.use_cases.sync_campaign_folder.execute(
            SyncCampaignFolderCommand(campaign_id=campaign_id),
        ),
        group="sync",
        thread=True,
        exit_on_error=False,
    )
