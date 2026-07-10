"""Campaign CLI commands."""

import typer

from notekeeper.application import (
    CreateCampaignCommand,
    GetCampaignCommand,
    ListCampaignsCommand,
    SyncCampaignFolderCommand,
)

from .common import RuntimeFactory, echo_campaign, echo_sync_result, run


def create_app(runtime_factory: RuntimeFactory) -> typer.Typer:
    app = typer.Typer(help="Manage campaigns.")

    @app.command("create")
    def create_campaign(name: str) -> None:
        runtime = runtime_factory()
        run(
            lambda: echo_campaign(
                runtime.use_cases.create_campaign.execute(
                    CreateCampaignCommand(name=name),
                ).campaign,
            ),
        )

    @app.command("list")
    def list_campaigns() -> None:
        runtime = runtime_factory()

        def action() -> None:
            result = runtime.use_cases.list_campaigns.execute(ListCampaignsCommand())
            for campaign in result.campaigns:
                echo_campaign(campaign)

        run(action)

    @app.command("show")
    def show_campaign(campaign_id: str) -> None:
        runtime = runtime_factory()

        def action() -> None:
            campaign = runtime.use_cases.get_campaign.execute(
                GetCampaignCommand(campaign_id=campaign_id),
            ).campaign
            echo_campaign(campaign)
            typer.echo(f"players={len(campaign.participants)}")
            typer.echo(f"voice_samples={len(campaign.voice_samples)}")
            typer.echo(f"recordings={len(campaign.audio_tracks)}")

        run(action)

    @app.command("sync")
    def sync_campaign(campaign_id: str) -> None:
        runtime = runtime_factory()

        def action() -> None:
            result = runtime.use_cases.sync_campaign_folder.execute(
                SyncCampaignFolderCommand(campaign_id=campaign_id),
            )
            echo_sync_result(result)

        run(action)

    return app
