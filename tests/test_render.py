from __future__ import annotations

from meeting_summarizer.models import ActionItem, CleanTranscript, FocusArea, FocusAreaReview, MeetingSummary, TalkPoint, TranscriptSegment
from meeting_summarizer.render import (
    derive_output_path,
    parse_cleaned_markdown,
    render_cleaned_markdown,
    render_focus_area_markdown,
    render_summary_markdown,
)


def test_derive_output_path_uses_sibling_file(workspace_tmp_path) -> None:
    transcript = workspace_tmp_path / "meeting.vtt"
    assert derive_output_path(transcript, ".summary.md") == workspace_tmp_path / "meeting.summary.md"


def test_render_markdown_outputs() -> None:
    cleaned = CleanTranscript(segments=[TranscriptSegment(speaker="Alice", text="Started meeting.", start_time="00:00:01")])
    summary = MeetingSummary(
        paragraph="The meeting covered tracking and operations.",
        themes=["tracking"],
        action_items=[ActionItem(mentioner="Alice", description="Follow up", quote="I'll follow up.")],
        resources=["example.com"],
        talk_points=[TalkPoint(speaker="Alice", salient_points=["Point"], questions=["Question"], quotes=["Quote"])],
    )
    review = FocusAreaReview(
        focus_area=FocusArea(id="tracking", title="Tracking", description="desc"),
        relevant_points=["Point"],
        outstanding_questions=["Question"],
        action_items=["Follow up"],
        quotes=["Quote"],
        coverage_note="Covered in detail.",
    )
    assert "# Cleaned Transcript" in render_cleaned_markdown(cleaned)
    assert "# Meeting Summary" in render_summary_markdown(summary)
    assert "# Focus Area Cross Reference" in render_focus_area_markdown([review])


def test_parse_cleaned_markdown_round_trips_segments() -> None:
    cleaned = CleanTranscript(
        segments=[
            TranscriptSegment(speaker="Alice", text="Started meeting.", start_time="00:00:01"),
            TranscriptSegment(speaker="Bob", text="Asked a question.\nSecond line."),
        ]
    )

    parsed = parse_cleaned_markdown(render_cleaned_markdown(cleaned))

    assert parsed == cleaned
