"""Participant CLI commands."""

import typer

from notekeeper.application import AddParticipantToCampaignCommand, ListParticipantsCommand

from .common import RuntimeFactory, echo_participant, run


def create_app(runtime_factory: RuntimeFactory) -> typer.Typer:
    app = typer.Typer(help="Manage campaign players.")

    @app.command("add")
    def add_participant(campaign_id: str, display_name: str) -> None:
        runtime = runtime_factory()
        run(
            lambda: echo_participant(
                runtime.use_cases.add_participant.execute(
                    AddParticipantToCampaignCommand(
                        campaign_id=campaign_id,
                        display_name=display_name,
                    ),
                ).participant,
            ),
        )

    @app.command("list")
    def list_participants(campaign_id: str) -> None:
        runtime = runtime_factory()

        def action() -> None:
            result = runtime.use_cases.list_participants.execute(
                ListParticipantsCommand(campaign_id=campaign_id),
            )
            for participant in result.participants:
                echo_participant(participant)

        run(action)

    return app
