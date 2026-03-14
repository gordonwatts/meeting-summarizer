from __future__ import annotations

from meeting_summarizer.analysis.pipeline import chunk_transcript_segments, clean_transcript, cross_reference_focus_areas, summarize_meeting
from meeting_summarizer.models import CleanTranscript, FocusArea, FocusAreaReview, MeetingSummary, ProjectConfig, SummaryTheme, TranscriptSegment
from meeting_summarizer.openai_client import cross_reference_with_llm, summarize_meeting_with_llm


class StubClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def generate_json(self, *, model: str, instructions: str, input_text: str):
        self.calls.append((instructions, input_text))
        if "Return JSON with a 'segments' array" in instructions:
            return {
                "segments": [
                    {
                        "speaker": "Alice",
                        "text": "Cleaned text.",
                        "start_time": "00:00:01",
                        "end_time": "00:00:02",
                        "source_lineage": ["Alice: raw"],
                    }
                ]
            }
        if "Analyze the cleaned meeting transcript" in instructions:
            return {
                "paragraph": "Summary paragraph.",
                "themes": ["theme"],
                "action_items": [{"mentioner": "Alice", "description": "Do thing", "quote": "Do thing"}],
                "resources": ["example.com"],
                "talk_points": [
                    {
                        "speaker": "Alice",
                        "salient_points": ["point"],
                        "questions": ["question"],
                        "quotes": ["quote"],
                    }
                ],
            }
        return {
            "relevant_points": ["point"],
            "outstanding_questions": ["question"],
            "action_items": ["Do thing"],
            "quotes": ["quote"],
            "coverage_note": "Covered.",
        }


def test_pipeline_uses_cleaned_output_for_summary_and_cross_reference() -> None:
    client = StubClient()
    segments = [TranscriptSegment(speaker="Alice", text="Raw text.")]
    cleaned = clean_transcript(segments, client, "gpt-5-mini")
    summary = summarize_meeting(cleaned, client, "gpt-5")
    reviews = cross_reference_focus_areas(summary, cleaned, ProjectConfig(name="Committee", focus_areas=[]), client, "gpt-5-mini")
    assert isinstance(cleaned, CleanTranscript)
    assert isinstance(summary, MeetingSummary)
    assert reviews == []
    assert "Cleaned text." in client.calls[1][1]


def test_cross_reference_returns_reviews() -> None:
    client = StubClient()
    cleaned = CleanTranscript(segments=[TranscriptSegment(speaker="Alice", text="Cleaned text.")])
    summary = MeetingSummary(
        paragraph="Summary paragraph.",
        themes=[SummaryTheme(title="theme")],
        action_items=[],
        resources=[],
        talk_points=[],
    )
    project = ProjectConfig(
        name="Committee",
        focus_areas=[FocusArea(id="tracking", title="Tracking", description="desc")],
    )
    reviews = cross_reference_focus_areas(summary, cleaned, project, client, "gpt-5-mini")
    assert len(reviews) == 1
    assert isinstance(reviews[0], FocusAreaReview)


def test_chunk_transcript_segments_walks_back_to_speaker_boundary() -> None:
    segments = [
        TranscriptSegment(speaker="Alice", start_time="00:00:01", text="A" * 40),
        TranscriptSegment(speaker="Bob", start_time="00:00:02", text="B" * 40),
        TranscriptSegment(speaker="Cara", start_time="00:00:03", text="C" * 40),
    ]
    chunks = chunk_transcript_segments(segments, max_chars=70)
    assert [[segment.speaker for segment in chunk] for chunk in chunks] == [
        ["Alice"],
        ["Bob"],
        ["Cara"],
    ]


def test_clean_transcript_cleans_multiple_chunks() -> None:
    client = StubClient()
    segments = [
        TranscriptSegment(speaker="Alice", start_time="00:00:01", text="A" * 40),
        TranscriptSegment(speaker="Bob", start_time="00:00:02", text="B" * 40),
        TranscriptSegment(speaker="Cara", start_time="00:00:03", text="C" * 40),
    ]
    cleaned = clean_transcript(segments, client, "gpt-5-mini", max_chunk_chars=70)
    clean_calls = [input_text for instructions, input_text in client.calls if "Return JSON with a 'segments' array" in instructions]
    assert len(clean_calls) == 3
    assert len(cleaned.segments) == 3


def test_cross_reference_normalizes_structured_review_items() -> None:
    class StructuredStubClient:
        def generate_json(self, *, model: str, instructions: str, input_text: str):
            return {
                "relevant_points": [{"speaker": "Alice", "text": "Raised validation requirements."}],
                "outstanding_questions": [{"title": "Validation", "description": "Who approves the standard?"}],
                "action_items": [
                    {
                        "owner": "Study group leads",
                        "task": "Draft acceptance criteria.",
                        "quote": "We should define the acceptance path.",
                    }
                ],
                "quotes": [{"speaker": "Alice", "quote": "We should define the acceptance path."}],
                "coverage_note": {"summary": "Covered at a high level."},
            }

    review = cross_reference_with_llm(
        StructuredStubClient(),
        "gpt-5-mini",
        MeetingSummary(paragraph="Summary paragraph.", themes=[], action_items=[], resources=[], talk_points=[]),
        CleanTranscript(segments=[TranscriptSegment(speaker="Alice", text="Cleaned text.")]),
        FocusArea(id="tracking", title="Tracking", description="desc"),
    )

    assert review.relevant_points == ["Alice: Raised validation requirements."]
    assert review.outstanding_questions == ["Validation: Who approves the standard?"]
    assert review.action_items == ['Study group leads: Draft acceptance criteria. Quote: "We should define the acceptance path."']
    assert review.quotes == ['Alice: "We should define the acceptance path."']
    assert review.coverage_note == "Covered at a high level."


def test_summary_normalizes_structured_themes_and_resources() -> None:
    class StructuredSummaryClient:
        def generate_json(self, *, model: str, instructions: str, input_text: str):
            return {
                "paragraph": "Summary paragraph.",
                "themes": [{"topic": "Coordination", "details": ["Shared tooling", "Training"]}],
                "action_items": [{"owner": "Alice", "description": "Follow up", "quote": "I will follow up."}],
                "resources": [{"name": "Indigo", "type": "portal", "context": "Meeting archive"}],
                "talk_points": [],
            }

    summary = summarize_meeting_with_llm(
        StructuredSummaryClient(),
        "gpt-5.4",
        CleanTranscript(segments=[TranscriptSegment(speaker="Alice", text="Cleaned text.")]),
    )

    assert summary.themes == [SummaryTheme(title="Coordination", details=["Shared tooling", "Training"])]
    assert summary.action_items[0].mentioner == "Alice"
    assert summary.resources[0].name == "Indigo"
