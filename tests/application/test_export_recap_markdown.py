from notekeeper.application import ExportRecapMarkdown, ExportRecapMarkdownCommand
from notekeeper.domain import ArtifactRef, Recap, RecapChunk, TimeRange


class RecapRepositoryStub:
    def __init__(self, recap: Recap) -> None:
        self._recap = recap

    def get(self, recap_id):
        return self._recap if recap_id == self._recap.id else None


class ArtifactStorageSpy:
    def __init__(self) -> None:
        self.content: str | None = None
        self.suggested_name: str | None = None
        self.media_type: str | None = None

    def save_text(
        self,
        *,
        suggested_name: str,
        content: str,
        media_type: str,
    ) -> ArtifactRef:
        self.content = content
        self.suggested_name = suggested_name
        self.media_type = media_type
        return ArtifactRef(uri=f"memory://{suggested_name}")


def test_export_recap_includes_ordered_chunks_before_overall_recap() -> None:
    recap = Recap(
        id="recap-1",
        transcript_id="transcript-1",
        markdown="# Session Recap\n\nOverall summary.",
        chunks=(
            RecapChunk(
                markdown="## First Part\n\nFirst chunk recap.",
                time_range=TimeRange(5, 65),
                source_segment_indexes=(3, 4),
            ),
            RecapChunk(
                markdown="## Second Part\n\nSecond chunk recap.",
                time_range=TimeRange(65, 3665),
                source_segment_indexes=(5, 6),
            ),
        ),
    )

    storage = _export(recap)

    assert storage.content == (
        "# Chunk 1\n\n"
        "**Time range:** 00:00:05 - 00:01:05\n\n"
        "## First Part\n\nFirst chunk recap.\n\n"
        "# Chunk 2\n\n"
        "**Time range:** 00:01:05 - 01:01:05\n\n"
        "## Second Part\n\nSecond chunk recap.\n\n"
        "# Overall Recap\n\n"
        "# Session Recap\n\nOverall summary.\n"
    )
    assert "# Chunk Recaps" not in storage.content
    assert "source_segment_indexes" not in storage.content
    assert storage.suggested_name == "recap-recap-1.md"
    assert storage.media_type == "text/markdown"


def test_export_recap_omits_missing_chunk_time_range() -> None:
    recap = Recap(
        id="recap-1",
        transcript_id="transcript-1",
        markdown="Overall summary.",
        chunks=(RecapChunk(markdown="Chunk without a time range."),),
    )

    storage = _export(recap)

    assert storage.content == (
        "# Chunk 1\n\n"
        "Chunk without a time range.\n\n"
        "# Overall Recap\n\n"
        "Overall summary.\n"
    )
    assert "Time range" not in storage.content


def test_export_legacy_recap_without_chunks_includes_only_overall_section() -> None:
    recap = Recap(
        id="recap-1",
        transcript_id="transcript-1",
        markdown="  # Session Recap\n\nOverall summary.  \n",
    )

    storage = _export(recap)

    assert storage.content == (
        "# Overall Recap\n\n# Session Recap\n\nOverall summary.\n"
    )
    assert "# Chunk Recaps" not in storage.content


def _export(recap: Recap) -> ArtifactStorageSpy:
    storage = ArtifactStorageSpy()
    ExportRecapMarkdown(RecapRepositoryStub(recap), storage).execute(
        ExportRecapMarkdownCommand(recap_id=recap.id),
    )
    return storage
