from __future__ import annotations

import logging

from typer.testing import CliRunner

from meeting_summarizer import cli
from meeting_summarizer.models import ActionItem, CleanTranscript, FocusArea, FocusAreaReview, MeetingSummary, TalkPoint, TranscriptSegment


class FakeClient:
    pass


def test_global_verbosity_sets_logging_level() -> None:
    runner = CliRunner()
    result = runner.invoke(cli.app, ["-vv", "project", "--help"])
    assert result.exit_code == 0
    assert logging.getLogger().level == logging.DEBUG


def test_project_show_resolves_yaml(sample_project) -> None:
    runner = CliRunner()
    result = runner.invoke(cli.app, ["project", "show", str(sample_project.with_suffix(""))])
    assert result.exit_code == 0
    assert "Tracking" in result.stdout


def test_analysis_writes_all_outputs(workspace_tmp_path, monkeypatch) -> None:
    transcript_path = workspace_tmp_path / "meeting.vtt"
    transcript_path.write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nAlice: Hi.\n",
        encoding="utf-8",
    )
    project_path = workspace_tmp_path / "project.yaml"
    project_path.write_text(
        "name: Committee\nfocus_areas:\n  - id: tracking\n    title: Tracking\n    description: desc\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(cli, "_make_client", lambda api_key: FakeClient())
    monkeypatch.setattr(
        cli,
        "clean_transcript",
        lambda segments, client, model: CleanTranscript(
            segments=[TranscriptSegment(speaker="Alice", text="Cleaned sentence.", start_time="00:00:01")]
        ),
    )
    monkeypatch.setattr(
        cli,
        "summarize_meeting",
        lambda cleaned, client, model: MeetingSummary(
            paragraph="Summary paragraph.",
            themes=["theme"],
            action_items=[ActionItem(mentioner="Alice", description="Do thing", quote="Do thing")],
            resources=["example.com"],
            talk_points=[TalkPoint(speaker="Alice", salient_points=["point"], questions=["question"], quotes=["quote"])],
        ),
    )
    monkeypatch.setattr(
        cli,
        "cross_reference_focus_areas",
        lambda summary, cleaned, project, client, model: [
            FocusAreaReview(
                focus_area=FocusArea(id="tracking", title="Tracking", description="desc"),
                relevant_points=["point"],
                outstanding_questions=["question"],
                action_items=["Do thing"],
                quotes=["quote"],
                coverage_note="Covered.",
            )
        ],
    )

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "transcript",
            "analysis",
            str(transcript_path),
            "--project",
            str(project_path),
            "--api-key",
            "secret",
            "--overwrite",
        ],
    )
    assert result.exit_code == 0
    assert (workspace_tmp_path / "meeting.cleaned.md").exists()
    assert (workspace_tmp_path / "meeting.summary.md").exists()
    assert (workspace_tmp_path / "meeting.focus-areas.md").exists()
