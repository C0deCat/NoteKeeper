"""Export recap markdown use case."""

from notekeeper.application.commands import ExportRecapMarkdownCommand
from notekeeper.application.ports import ArtifactStorage, RecapRepository
from notekeeper.application.results import ExportMarkdownResult
from notekeeper.application.use_cases.utils import _require_recap
from notekeeper.domain import RecapId

from ._markdown import render_recap_markdown


class ExportRecapMarkdown:
    def __init__(
        self,
        recap_repository: RecapRepository,
        artifact_storage: ArtifactStorage,
    ) -> None:
        self._recap_repository = recap_repository
        self._artifact_storage = artifact_storage

    def execute(self, command: ExportRecapMarkdownCommand) -> ExportMarkdownResult:
        recap = _require_recap(self._recap_repository, RecapId(command.recap_id))
        artifact = self._artifact_storage.save_text(
            suggested_name=f"recap-{recap.id}.md",
            content=render_recap_markdown(recap),
            media_type="text/markdown",
        )
        return ExportMarkdownResult(artifact=artifact)
