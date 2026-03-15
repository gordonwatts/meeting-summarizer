from __future__ import annotations

from pathlib import Path

from meeting_summarizer.models import (
    CleanTranscript,
    FocusArea,
    ProjectConfig,
    SummaryTheme,
    TalkPoint,
    TranscriptSegment,
)


def test_models_default_optional_fields() -> None:
    segment = TranscriptSegment(speaker="Alice", text="Hello")
    assert segment.start_time is None
    assert segment.source_lineage == []

    theme = SummaryTheme(title="Coordination")
    assert theme.details == []

    talk = TalkPoint(speaker="Alice", salient_points=[], questions=[])
    assert talk.quotes == []


def test_project_config_tracks_models_and_path() -> None:
    project = ProjectConfig(
        name="Committee",
        focus_areas=[FocusArea(id="tracking", title="Tracking", description="desc")],
        models={"economy": "gpt-5-mini"},
        path=Path("project.yaml"),
    )
    cleaned = CleanTranscript(segments=[TranscriptSegment(speaker="Alice", text="Hi")])

    assert project.models["economy"] == "gpt-5-mini"
    assert project.path == Path("project.yaml")
    assert cleaned.segments[0].speaker == "Alice"
