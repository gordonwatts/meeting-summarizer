from __future__ import annotations

from meeting_summarizer.analysis.pipeline import chunk_transcript_segments, clean_transcript, cross_reference_focus_areas, summarize_meeting
from meeting_summarizer.models import CleanTranscript, FocusArea, FocusAreaReview, MeetingSummary, ProjectConfig, TranscriptSegment


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
        themes=["theme"],
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
