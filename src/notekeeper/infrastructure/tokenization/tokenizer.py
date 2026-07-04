"""tiktoken-based transcript tokenizer."""

from __future__ import annotations

from notekeeper.application.ports import Tokenizer
from notekeeper.application.results import TranscriptChunk
from notekeeper.domain import TimeRange, Transcript, TranscriptSegment
from notekeeper.infrastructure.errors import InfrastructureError

try:
    import tiktoken
except ImportError as exc:  # pragma: no cover - dependency is declared by project.
    tiktoken = None
    _TIKTOKEN_IMPORT_ERROR = exc
else:
    _TIKTOKEN_IMPORT_ERROR = None


class TiktokenTranscriptTokenizer(Tokenizer):
    def __init__(
        self,
        *,
        encoding_name: str = "cl100k_base",
        max_token_count: int = 35_000,
    ) -> None:
        self._max_token_count = self._require_positive_int(
            max_token_count,
            "max_token_count",
        )
        self._encoding_name = self._require_text(encoding_name, "encoding_name")
        self._encoding = self._load_encoding(self._encoding_name)

    def split_transcript(
        self,
        transcript: Transcript,
        *,
        target_token_count: int,
    ) -> tuple[TranscriptChunk, ...]:
        target_token_count = self._require_positive_int(
            target_token_count,
            "target_token_count",
        )
        if not transcript.segments:
            return (TranscriptChunk(text=""),)

        chunk_limit = min(target_token_count, self._max_token_count)
        chunks: list[TranscriptChunk] = []
        current_lines: list[str] = []
        current_segments: list[TranscriptSegment] = []
        current_token_count = 0

        for segment in transcript.segments:
            line = self._render_segment(segment)
            token_count = self._token_count(line)

            if token_count > self._max_token_count:
                if current_lines:
                    chunks.append(
                        self._build_chunk(current_lines, current_segments),
                    )
                    current_lines = []
                    current_segments = []
                    current_token_count = 0
                chunks.extend(self._split_long_segment(segment))
                continue

            if current_lines and current_token_count + token_count > chunk_limit:
                chunks.append(self._build_chunk(current_lines, current_segments))
                current_lines = []
                current_segments = []
                current_token_count = 0

            current_lines.append(line)
            current_segments.append(segment)
            current_token_count += token_count

        if current_lines:
            chunks.append(self._build_chunk(current_lines, current_segments))

        return tuple(chunks)

    def _split_long_segment(
        self,
        segment: TranscriptSegment,
    ) -> tuple[TranscriptChunk, ...]:
        prefix = self._segment_prefix(segment)
        prefix_token_count = self._token_count(prefix)
        text_token_budget = max(1, self._max_token_count - prefix_token_count)
        text_tokens = self._encoding.encode(segment.text)
        chunks = []

        for start in range(0, len(text_tokens), text_token_budget):
            text_slice = text_tokens[start : start + text_token_budget]
            text = self._encoding.decode(text_slice).strip()
            chunks.append(
                TranscriptChunk(
                    text=f"{prefix}{text}".rstrip(),
                    segments=(segment,),
                    time_range=segment.time_range,
                    source_segment_indexes=(segment.index,),
                ),
            )

        return tuple(chunks)

    def _build_chunk(
        self,
        lines: list[str],
        segments: list[TranscriptSegment],
    ) -> TranscriptChunk:
        return TranscriptChunk(
            text="\n".join(lines),
            segments=tuple(segments),
            time_range=self._time_range_for_segments(segments),
            source_segment_indexes=tuple(segment.index for segment in segments),
        )

    def _time_range_for_segments(
        self,
        segments: list[TranscriptSegment],
    ) -> TimeRange | None:
        if not segments:
            return None
        return TimeRange(
            start_seconds=segments[0].time_range.start_seconds,
            end_seconds=segments[-1].time_range.end_seconds,
        )

    def _render_segment(self, segment: TranscriptSegment) -> str:
        return f"{self._segment_prefix(segment)}{segment.text}"

    def _segment_prefix(self, segment: TranscriptSegment) -> str:
        start = self._format_seconds(segment.time_range.start_seconds)
        end = self._format_seconds(segment.time_range.end_seconds)
        return f"[{start} - {end}] **{segment.speaker_label.value}:** "

    def _token_count(self, text: str) -> int:
        return len(self._encoding.encode(text))

    def _load_encoding(self, encoding_name: str):
        if tiktoken is None:
            raise InfrastructureError("tiktoken is not installed") from (
                _TIKTOKEN_IMPORT_ERROR
            )
        try:
            return tiktoken.get_encoding(encoding_name)
        except Exception as exc:
            raise InfrastructureError(
                f"could not load tokenizer encoding: {encoding_name}",
            ) from exc

    def _format_seconds(self, seconds: float) -> str:
        total_seconds = int(seconds)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _require_text(self, value: str, field: str) -> str:
        text = value.strip()
        if not text:
            raise InfrastructureError(f"{field} must not be empty")
        return text

    def _require_positive_int(self, value: int, field: str) -> int:
        if not isinstance(value, int) or value <= 0:
            raise InfrastructureError(f"{field} must be a positive integer")
        return value


__all__ = ["TiktokenTranscriptTokenizer"]
