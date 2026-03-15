from __future__ import annotations

from meeting_summarizer.markdown.cleaned import (
    parse_cleaned_markdown,
    render_cleaned_markdown,
)
from meeting_summarizer.models import CleanTranscript, TranscriptSegment


def test_render_cleaned_markdown_outputs_heading() -> None:
    cleaned = CleanTranscript(
        segments=[
            TranscriptSegment(
                speaker="Alice", text="Started meeting.", start_time="00:00:01"
            )
        ]
    )
    assert "# Cleaned Transcript" in render_cleaned_markdown(cleaned)


def test_parse_cleaned_markdown_round_trips_segments() -> None:
    cleaned = CleanTranscript(
        segments=[
            TranscriptSegment(
                speaker="Alice", text="Started meeting.", start_time="00:00:01"
            ),
            TranscriptSegment(speaker="Bob", text="Asked a question.\nSecond line."),
        ]
    )
    assert parse_cleaned_markdown(render_cleaned_markdown(cleaned)) == cleaned
