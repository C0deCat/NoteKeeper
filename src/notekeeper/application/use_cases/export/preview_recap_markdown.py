"""Preview recap Markdown use case."""

from notekeeper.application.commands import PreviewRecapMarkdownCommand
from notekeeper.application.ports import RecapRepository
from notekeeper.application.results import MarkdownPreviewResult
from notekeeper.application.use_cases.utils import _require_recap
from notekeeper.domain import RecapId


class PreviewRecapMarkdown:
    def __init__(self, recap_repository: RecapRepository) -> None:
        self._recap_repository = recap_repository

    def execute(self, command: PreviewRecapMarkdownCommand) -> MarkdownPreviewResult:
        recap = _require_recap(self._recap_repository, RecapId(command.recap_id))
        return MarkdownPreviewResult(markdown=recap.markdown)
