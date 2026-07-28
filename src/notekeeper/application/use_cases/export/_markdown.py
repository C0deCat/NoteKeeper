"""Markdown rendering helpers."""

from notekeeper.domain import Recap, Transcript


def render_recap_markdown(recap: Recap) -> str:
    sections: list[str] = []

    if recap.chunks:
        for index, chunk in enumerate(recap.chunks, start=1):
            chunk_lines = [f"# Chunk {index}"]
            if chunk.time_range is not None:
                start = format_seconds(chunk.time_range.start_seconds)
                end = format_seconds(chunk.time_range.end_seconds)
                chunk_lines.extend(("", f"**Time range:** {start} - {end}"))
            chunk_lines.extend(("", chunk.markdown.strip()))
            sections.append("\n".join(chunk_lines))

    sections.extend(("# Overall Recap", recap.markdown.strip()))
    return "\n\n".join(sections).rstrip() + "\n"


def render_transcript_markdown(transcript: Transcript) -> str:
    sections = ["# Transcript"]
    for segment in transcript.segments:
        start = format_seconds(segment.time_range.start_seconds)
        end = format_seconds(segment.time_range.end_seconds)
        speaker = segment.speaker_label.value
        sections.append(f"[{start} - {end}] **{speaker}:** {segment.text}")
    return "\n\n".join(sections).rstrip() + "\n"


def format_seconds(seconds: float) -> str:
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
