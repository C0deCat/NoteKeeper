"""Markdown rendering helpers."""

from notekeeper.domain import Transcript


def render_transcript_markdown(transcript: Transcript) -> str:
    lines = ["# Transcript", ""]
    for segment in transcript.segments:
        start = format_seconds(segment.time_range.start_seconds)
        end = format_seconds(segment.time_range.end_seconds)
        speaker = segment.speaker_label.value
        lines.append(f"[{start} - {end}] **{speaker}:** {segment.text}")
    return "\n".join(lines).rstrip() + "\n"


def format_seconds(seconds: float) -> str:
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
