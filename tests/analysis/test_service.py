from __future__ import annotations

from meeting_summarizer.analysis import service
from meeting_summarizer.analysis.service import TranscriptAnalysisService
from meeting_summarizer.models import (
    CleanTranscript,
    FocusArea,
    FocusAreaReview,
    MeetingSummary,
    TranscriptSegment,
)


class DummyClient:
    pass


def test_output_paths_match_expected_suffixes(workspace_tmp_path) -> None:
    svc = TranscriptAnalysisService(DummyClient())
    paths = svc.output_paths(workspace_tmp_path / "meeting.vtt")
    assert paths.cleaned_path.name == "meeting.cleaned.md"
    assert paths.summary_path.name == "meeting.summary.md"
    assert paths.focus_path.name == "meeting.focus-areas.md"


def test_clean_transcript_reuses_existing_markdown(workspace_tmp_path) -> None:
    transcript_path = workspace_tmp_path / "meeting.vtt"
    transcript_path.write_text("WEBVTT\n", encoding="utf-8")
    cleaned_path = workspace_tmp_path / "meeting.cleaned.md"
    cleaned_path.write_text(
        "# Cleaned Transcript\n\n## Alice (00:00:01)\n\nExisting cleaned text.\n",
        encoding="utf-8",
    )

    svc = TranscriptAnalysisService(DummyClient())
    cleaned, path, reused = svc.clean_transcript(
        transcript_path,
        output_dir=None,
        model="gpt-5-mini",
        max_clean_chars=100,
        overwrite=False,
    )
    assert reused is True
    assert path == cleaned_path
    assert cleaned.segments[0].text == "Existing cleaned text."


def test_cross_reference_writes_output(workspace_tmp_path, monkeypatch) -> None:
    transcript_path = workspace_tmp_path / "meeting.vtt"
    transcript_path.write_text("WEBVTT\n", encoding="utf-8")
    project_path = workspace_tmp_path / "project.yaml"
    project_path.write_text(
        "name: Committee\nfocus_areas:\n  - id: tracking\n    title: Tracking\n    description: desc\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        service,
        "cross_reference_focus_areas",
        lambda summary, cleaned, project, client, model: [
            FocusAreaReview(
                focus_area=FocusArea(
                    id="tracking", title="Tracking", description="desc"
                ),
                mentioned_people=["Alice"],
                relevant_points=["point"],
                outstanding_questions=[],
                action_items=[],
                quotes=[],
                coverage_note="Covered.",
            )
        ],
    )

    svc = TranscriptAnalysisService(DummyClient())
    reviews, focus_path = svc.cross_reference_focus_areas(
        transcript_path,
        project_path=project_path,
        output_dir=None,
        summary=MeetingSummary(
            paragraph="Summary paragraph.",
            themes=[],
            action_items=[],
            resources=[],
            talk_points=[],
        ),
        cleaned=CleanTranscript(
            segments=[TranscriptSegment(speaker="Alice", text="Cleaned text.")]
        ),
        model="gpt-5-mini",
        overwrite=True,
    )
    assert len(reviews) == 1
    assert focus_path.exists()


def test_run_full_analysis_returns_without_work_when_outputs_exist(
    workspace_tmp_path,
) -> None:
    cleaned_path = workspace_tmp_path / "meeting.cleaned.md"
    cleaned_path.write_text(
        "# Cleaned Transcript\n\n## Alice (00:00:01)\n\nExisting cleaned text.\n",
        encoding="utf-8",
    )
    summary_path = workspace_tmp_path / "meeting.summary.md"
    summary_path.write_text(
        "# Meeting Summary\n\nSummary paragraph.\n\n## Themes\n\n- None noted.\n\n## Action Items\n\n| Owner | Action | Quote |\n| --- | --- | --- |\n| None noted. |  |  |\n\n## External Resources\n\n| Resource | Type | Context |\n| --- | --- | --- |\n| None noted. |  |  |\n\n## Talk Highlights\n",
        encoding="utf-8",
    )
    (workspace_tmp_path / "meeting.focus-areas.md").write_text(
        "# Focus Area Cross Reference\n", encoding="utf-8"
    )
    project_path = workspace_tmp_path / "project.yaml"
    project_path.write_text(
        "name: Committee\nfocus_areas:\n  - id: tracking\n    title: Tracking\n    description: desc\n",
        encoding="utf-8",
    )

    svc = TranscriptAnalysisService(DummyClient())
    artifacts = svc.run_full_analysis(
        workspace_tmp_path / "meeting.vtt",
        project_path=project_path,
        output_dir=None,
        economy_model="gpt-5-mini",
        judgment_model="gpt-5.4",
        max_clean_chars=100,
        overwrite=False,
    )
    assert artifacts.cleaned.segments[0].text == "Existing cleaned text."
    assert artifacts.summary is not None
