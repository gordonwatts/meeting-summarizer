from __future__ import annotations

from meeting_summarizer.analysis.llm_stages import (
    cross_reference_with_llm,
    summarize_meeting_with_llm,
    transcript_to_text,
)
from meeting_summarizer.models import (
    CleanTranscript,
    FocusArea,
    MeetingSummary,
    SummaryTheme,
    TranscriptSegment,
)


def test_transcript_to_text_includes_timestamps() -> None:
    text = transcript_to_text(
        [TranscriptSegment(speaker="Alice", text="Cleaned text.", start_time="00:00:01")]
    )
    assert text == "Alice [00:00:01]: Cleaned text."


def test_cross_reference_normalizes_structured_review_items() -> None:
    class StructuredStubClient:
        def generate_json(self, *, model: str, instructions: str, input_text: str):
            return {
                "relevant_points": [
                    {"speaker": "Alice", "text": "Raised validation requirements."}
                ],
                "outstanding_questions": [
                    {"title": "Validation", "description": "Who approves the standard?"}
                ],
                "action_items": [
                    {
                        "owner": "Study group leads",
                        "task": "Draft acceptance criteria.",
                        "quote": "We should define the acceptance path.",
                    }
                ],
                "quotes": [
                    {
                        "speaker": "Alice",
                        "quote": "We should define the acceptance path.",
                    }
                ],
                "coverage_note": {"summary": "Covered at a high level."},
            }

    review = cross_reference_with_llm(
        StructuredStubClient(),
        "gpt-5-mini",
        MeetingSummary(
            paragraph="Summary paragraph.",
            themes=[],
            action_items=[],
            resources=[],
            talk_points=[],
        ),
        CleanTranscript(
            segments=[TranscriptSegment(speaker="Alice", text="Cleaned text.")]
        ),
        FocusArea(id="tracking", title="Tracking", description="desc"),
    )

    assert review.relevant_points == ["Alice: Raised validation requirements."]
    assert review.outstanding_questions == ["Validation: Who approves the standard?"]
    assert review.action_items == [
        'Study group leads: Draft acceptance criteria. Quote: "We should define the acceptance path."'
    ]
    assert review.quotes == ['Alice: "We should define the acceptance path."']
    assert review.coverage_note == "Covered at a high level."


def test_summary_normalizes_structured_themes_and_resources() -> None:
    class StructuredSummaryClient:
        def generate_json(self, *, model: str, instructions: str, input_text: str):
            return {
                "paragraph": "Summary paragraph.",
                "themes": [
                    {"topic": "Coordination", "details": ["Shared tooling", "Training"]}
                ],
                "action_items": [
                    {
                        "owner": "Alice",
                        "description": "Follow up",
                        "quote": "I will follow up.",
                    }
                ],
                "resources": [
                    {"name": "Indigo", "type": "portal", "context": "Meeting archive"}
                ],
                "talk_points": [],
            }

    summary = summarize_meeting_with_llm(
        StructuredSummaryClient(),
        "gpt-5.4",
        CleanTranscript(
            segments=[TranscriptSegment(speaker="Alice", text="Cleaned text.")]
        ),
    )

    assert summary.themes == [
        SummaryTheme(title="Coordination", details=["Shared tooling", "Training"])
    ]
    assert summary.action_items[0].mentioner == "Alice"
    assert summary.resources[0].name == "Indigo"
