from __future__ import annotations

import logging

from typer.testing import CliRunner

from meeting_summarizer import cli
from meeting_summarizer.models import (
    ActionItem,
    CleanTranscript,
    ExternalResource,
    FocusArea,
    FocusAreaReview,
    MeetingSummary,
    SummaryTheme,
    TalkPoint,
    TranscriptSegment,
)


class FakeClient:
    pass


SUMMARY_MARKDOWN = (
    "# Meeting Summary\n\n"
    "Existing summary paragraph.\n\n"
    "## Themes\n\n"
    "| Theme | Details |\n"
    "| --- | --- |\n"
    "| tracking | |\n\n"
    "## Action Items\n\n"
    "| Owner | Action | Quote |\n"
    "| --- | --- | --- |\n"
    "| None noted. |  |  |\n\n"
    "## External Resources\n\n"
    "| Resource | Type | Context |\n"
    "| --- | --- | --- |\n"
    "| None noted. |  |  |\n\n"
    "## Talk Highlights\n"
)


def test_global_verbosity_sets_logging_level() -> None:
    runner = CliRunner()
    result = runner.invoke(cli.app, ["-vv", "project", "--help"])
    assert result.exit_code == 0
    assert logging.getLogger().level == logging.DEBUG


def test_project_show_resolves_yaml(sample_project) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli.app, ["project", "show", str(sample_project.with_suffix(""))]
    )
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
        lambda segments, client, model, max_chunk_chars=15000: CleanTranscript(
            segments=[
                TranscriptSegment(
                    speaker="Alice", text="Cleaned sentence.", start_time="00:00:01"
                )
            ]
        ),
    )
    monkeypatch.setattr(
        cli,
        "summarize_meeting",
        lambda cleaned, client, model: MeetingSummary(
            paragraph="Summary paragraph.",
            themes=[SummaryTheme(title="theme")],
            action_items=[
                ActionItem(mentioner="Alice", description="Do thing", quote="Do thing")
            ],
            resources=[ExternalResource(name="example.com")],
            talk_points=[
                TalkPoint(
                    speaker="Alice",
                    salient_points=["point"],
                    questions=["question"],
                    quotes=["quote"],
                )
            ],
        ),
    )
    monkeypatch.setattr(
        cli,
        "cross_reference_focus_areas",
        lambda summary, cleaned, project, client, model: [
            FocusAreaReview(
                focus_area=FocusArea(
                    id="tracking", title="Tracking", description="desc"
                ),
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
    assert result.stdout == ""
    assert (workspace_tmp_path / "meeting.cleaned.md").exists()
    assert (workspace_tmp_path / "meeting.summary.md").exists()
    assert (workspace_tmp_path / "meeting.focus-areas.md").exists()


def test_clean_command_passes_max_clean_chars(workspace_tmp_path, monkeypatch) -> None:
    transcript_path = workspace_tmp_path / "meeting.vtt"
    transcript_path.write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nAlice: Hi.\n",
        encoding="utf-8",
    )

    captured: dict[str, int] = {}
    monkeypatch.setattr(cli, "_make_client", lambda api_key: FakeClient())

    def fake_clean_transcript(segments, client, model, max_chunk_chars=15000):
        captured["max_chunk_chars"] = max_chunk_chars
        return CleanTranscript(
            segments=[
                TranscriptSegment(
                    speaker="Alice", text="Cleaned sentence.", start_time="00:00:01"
                )
            ]
        )

    monkeypatch.setattr(cli, "clean_transcript", fake_clean_transcript)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "transcript",
            "clean",
            str(transcript_path),
            "--api-key",
            "secret",
            "--overwrite",
            "--max-clean-chars",
            "321",
        ],
    )
    assert result.exit_code == 0
    assert result.stdout == ""
    assert captured["max_chunk_chars"] == 321


def test_clean_fails_when_existing_output_before_creating_client(
    workspace_tmp_path, monkeypatch
) -> None:
    transcript_path = workspace_tmp_path / "meeting.vtt"
    transcript_path.write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nAlice: Hi.\n",
        encoding="utf-8",
    )
    cleaned_path = workspace_tmp_path / "meeting.cleaned.md"
    cleaned_path.write_text("# Cleaned Transcript\n", encoding="utf-8")

    def fail_make_client(*args, **kwargs):
        raise AssertionError(
            "_make_client should not be called when cleaned output already exists"
        )

    monkeypatch.setattr(cli, "_make_client", fail_make_client)

    runner = CliRunner()
    result = runner.invoke(
        cli.app, ["transcript", "clean", str(transcript_path), "--api-key", "secret"]
    )

    assert result.exit_code != 0


def test_summarize_reuses_existing_cleaned_markdown(
    workspace_tmp_path, monkeypatch
) -> None:
    transcript_path = workspace_tmp_path / "meeting.vtt"
    transcript_path.write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nAlice: Hi.\n",
        encoding="utf-8",
    )
    cleaned_path = workspace_tmp_path / "meeting.cleaned.md"
    cleaned_path.write_text(
        "# Cleaned Transcript\n\n## Alice (00:00:01)\n\nExisting cleaned text.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(cli, "_make_client", lambda api_key: FakeClient())

    def fail_clean_transcript(*args, **kwargs):
        raise AssertionError(
            "clean_transcript should not be called when cleaned markdown exists"
        )

    monkeypatch.setattr(cli, "clean_transcript", fail_clean_transcript)
    monkeypatch.setattr(
        cli,
        "summarize_meeting",
        lambda cleaned, client, model: MeetingSummary(
            paragraph=cleaned.segments[0].text,
            themes=[],
            action_items=[],
            resources=[],
            talk_points=[],
        ),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "transcript",
            "summarize",
            str(transcript_path),
            "--api-key",
            "secret",
        ],
    )

    assert result.exit_code == 0
    assert result.stdout == ""
    assert "Existing cleaned text." in (
        workspace_tmp_path / "meeting.summary.md"
    ).read_text(encoding="utf-8")


def test_summarize_fails_when_existing_summary_markdown(
    workspace_tmp_path, monkeypatch
) -> None:
    transcript_path = workspace_tmp_path / "meeting.vtt"
    transcript_path.write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nAlice: Hi.\n",
        encoding="utf-8",
    )
    (workspace_tmp_path / "meeting.cleaned.md").write_text(
        "# Cleaned Transcript\n\n## Alice (00:00:01)\n\nExisting cleaned text.\n",
        encoding="utf-8",
    )
    summary_path = workspace_tmp_path / "meeting.summary.md"
    summary_path.write_text(SUMMARY_MARKDOWN, encoding="utf-8")

    def fail_make_client(*args, **kwargs):
        raise AssertionError(
            "_make_client should not be called when summary output already exists"
        )

    monkeypatch.setattr(cli, "_make_client", fail_make_client)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "transcript",
            "summarize",
            str(transcript_path),
            "--api-key",
            "secret",
        ],
    )

    assert result.exit_code != 0


def test_summarize_cleans_when_cleaned_markdown_missing(
    workspace_tmp_path, monkeypatch
) -> None:
    transcript_path = workspace_tmp_path / "meeting.vtt"
    transcript_path.write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nAlice: Hi.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(cli, "_make_client", lambda api_key: FakeClient())
    monkeypatch.setattr(
        cli,
        "clean_transcript",
        lambda segments, client, model, max_chunk_chars=15000: CleanTranscript(
            segments=[
                TranscriptSegment(
                    speaker="Alice", text="Fresh cleaned text.", start_time="00:00:01"
                )
            ]
        ),
    )
    monkeypatch.setattr(
        cli,
        "summarize_meeting",
        lambda cleaned, client, model: MeetingSummary(
            paragraph=cleaned.segments[0].text,
            themes=[],
            action_items=[],
            resources=[],
            talk_points=[],
        ),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "transcript",
            "summarize",
            str(transcript_path),
            "--api-key",
            "secret",
        ],
    )

    assert result.exit_code == 0
    assert result.stdout == ""
    assert (workspace_tmp_path / "meeting.cleaned.md").exists()
    assert "Fresh cleaned text." in (
        workspace_tmp_path / "meeting.summary.md"
    ).read_text(encoding="utf-8")


def test_cross_reference_reuses_existing_cleaned_markdown(
    workspace_tmp_path, monkeypatch
) -> None:
    transcript_path = workspace_tmp_path / "meeting.vtt"
    transcript_path.write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nAlice: Hi.\n",
        encoding="utf-8",
    )
    cleaned_path = workspace_tmp_path / "meeting.cleaned.md"
    cleaned_path.write_text(
        "# Cleaned Transcript\n\n## Alice (00:00:01)\n\nExisting cleaned text.\n",
        encoding="utf-8",
    )
    (workspace_tmp_path / "meeting.summary.md").write_text(
        SUMMARY_MARKDOWN, encoding="utf-8"
    )
    project_path = workspace_tmp_path / "project.yaml"
    project_path.write_text(
        "name: Committee\nfocus_areas:\n  - id: tracking\n    title: Tracking\n    description: desc\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(cli, "_make_client", lambda api_key: FakeClient())

    def fail_clean_transcript(*args, **kwargs):
        raise AssertionError(
            "clean_transcript should not be called when cleaned markdown exists"
        )

    monkeypatch.setattr(cli, "clean_transcript", fail_clean_transcript)

    def fail_summarize_meeting(*args, **kwargs):
        raise AssertionError(
            "summarize_meeting should not be called when summary markdown exists"
        )

    monkeypatch.setattr(cli, "summarize_meeting", fail_summarize_meeting)
    monkeypatch.setattr(
        cli,
        "cross_reference_focus_areas",
        lambda summary, cleaned, project, client, model: [
            FocusAreaReview(
                focus_area=FocusArea(
                    id="tracking", title="Tracking", description="desc"
                ),
                relevant_points=[summary.paragraph, cleaned.segments[0].text],
                outstanding_questions=[],
                action_items=[],
                quotes=[],
                coverage_note="Covered.",
            )
        ],
    )

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "transcript",
            "cross-reference",
            str(transcript_path),
            "--project",
            str(project_path),
            "--api-key",
            "secret",
        ],
    )

    assert result.exit_code == 0
    assert result.stdout == ""
    assert "Existing summary paragraph." in (
        workspace_tmp_path / "meeting.focus-areas.md"
    ).read_text(encoding="utf-8")
    assert "Existing cleaned text." in (
        workspace_tmp_path / "meeting.focus-areas.md"
    ).read_text(encoding="utf-8")


def test_cross_reference_fails_when_existing_focus_output_before_creating_client(
    workspace_tmp_path, monkeypatch
) -> None:
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
    focus_path = workspace_tmp_path / "meeting.focus-areas.md"
    focus_path.write_text("# Focus Area Cross Reference\n", encoding="utf-8")

    def fail_make_client(*args, **kwargs):
        raise AssertionError(
            "_make_client should not be called when focus-area output already exists"
        )

    monkeypatch.setattr(cli, "_make_client", fail_make_client)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "transcript",
            "cross-reference",
            str(transcript_path),
            "--project",
            str(project_path),
            "--api-key",
            "secret",
        ],
    )

    assert result.exit_code != 0


def test_analysis_reuses_existing_cleaned_markdown(
    workspace_tmp_path, monkeypatch
) -> None:
    transcript_path = workspace_tmp_path / "meeting.vtt"
    transcript_path.write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nAlice: Hi.\n",
        encoding="utf-8",
    )
    cleaned_path = workspace_tmp_path / "meeting.cleaned.md"
    cleaned_path.write_text(
        "# Cleaned Transcript\n\n## Alice (00:00:01)\n\nExisting cleaned text.\n",
        encoding="utf-8",
    )
    (workspace_tmp_path / "meeting.summary.md").write_text(
        SUMMARY_MARKDOWN, encoding="utf-8"
    )
    project_path = workspace_tmp_path / "project.yaml"
    project_path.write_text(
        "name: Committee\nfocus_areas:\n  - id: tracking\n    title: Tracking\n    description: desc\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(cli, "_make_client", lambda api_key: FakeClient())

    def fail_clean_transcript(*args, **kwargs):
        raise AssertionError(
            "clean_transcript should not be called when cleaned markdown exists"
        )

    monkeypatch.setattr(cli, "clean_transcript", fail_clean_transcript)

    def fail_summarize_meeting(*args, **kwargs):
        raise AssertionError(
            "summarize_meeting should not be called when summary markdown exists"
        )

    monkeypatch.setattr(cli, "summarize_meeting", fail_summarize_meeting)
    monkeypatch.setattr(
        cli,
        "cross_reference_focus_areas",
        lambda summary, cleaned, project, client, model: [
            FocusAreaReview(
                focus_area=FocusArea(
                    id="tracking", title="Tracking", description="desc"
                ),
                relevant_points=[summary.paragraph, cleaned.segments[0].text],
                outstanding_questions=[],
                action_items=[],
                quotes=[],
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
        ],
    )

    assert result.exit_code == 0
    assert result.stdout == ""
    assert "Existing summary paragraph." in (
        workspace_tmp_path / "meeting.focus-areas.md"
    ).read_text(encoding="utf-8")
    assert "Existing cleaned text." in (
        workspace_tmp_path / "meeting.focus-areas.md"
    ).read_text(encoding="utf-8")


def test_analysis_returns_existing_outputs_before_creating_client(
    workspace_tmp_path, monkeypatch
) -> None:
    transcript_path = workspace_tmp_path / "meeting.vtt"
    transcript_path.write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nAlice: Hi.\n",
        encoding="utf-8",
    )
    (workspace_tmp_path / "meeting.cleaned.md").write_text(
        "# Cleaned Transcript\n", encoding="utf-8"
    )
    (workspace_tmp_path / "meeting.summary.md").write_text(
        SUMMARY_MARKDOWN, encoding="utf-8"
    )
    focus_path = workspace_tmp_path / "meeting.focus-areas.md"
    focus_path.write_text("# Focus Area Cross Reference\n", encoding="utf-8")
    project_path = workspace_tmp_path / "project.yaml"
    project_path.write_text(
        "name: Committee\nfocus_areas:\n  - id: tracking\n    title: Tracking\n    description: desc\n",
        encoding="utf-8",
    )

    def fail_make_client(*args, **kwargs):
        raise AssertionError(
            "_make_client should not be called when all outputs already exist"
        )

    monkeypatch.setattr(cli, "_make_client", fail_make_client)

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
        ],
    )

    assert result.exit_code == 0
    assert result.stdout == ""


def test_analysis_reuses_existing_focus_output_and_generates_missing_dependencies(
    workspace_tmp_path, monkeypatch
) -> None:
    transcript_path = workspace_tmp_path / "meeting.vtt"
    transcript_path.write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nAlice: Hi.\n",
        encoding="utf-8",
    )
    focus_path = workspace_tmp_path / "meeting.focus-areas.md"
    focus_path.write_text("# Focus Area Cross Reference\n", encoding="utf-8")
    project_path = workspace_tmp_path / "project.yaml"
    project_path.write_text(
        "name: Committee\nfocus_areas:\n  - id: tracking\n    title: Tracking\n    description: desc\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(cli, "_make_client", lambda api_key: FakeClient())
    monkeypatch.setattr(
        cli,
        "clean_transcript",
        lambda segments, client, model, max_chunk_chars=15000: CleanTranscript(
            segments=[
                TranscriptSegment(
                    speaker="Alice", text="Cleaned sentence.", start_time="00:00:01"
                )
            ]
        ),
    )
    monkeypatch.setattr(
        cli,
        "summarize_meeting",
        lambda cleaned, client, model: MeetingSummary(
            paragraph="Summary paragraph.",
            themes=[SummaryTheme(title="theme")],
            action_items=[],
            resources=[],
            talk_points=[],
        ),
    )
    cross_reference_calls = {"count": 0}

    def fake_cross_reference(summary, cleaned, project, client, model):
        cross_reference_calls["count"] += 1
        return [
            FocusAreaReview(
                focus_area=FocusArea(
                    id="tracking", title="Tracking", description="desc"
                ),
                relevant_points=["point"],
                outstanding_questions=[],
                action_items=[],
                quotes=[],
                coverage_note="Covered.",
            )
        ]

    monkeypatch.setattr(cli, "cross_reference_focus_areas", fake_cross_reference)

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
        ],
    )

    assert result.exit_code == 0
    assert result.stdout == ""
    assert (workspace_tmp_path / "meeting.cleaned.md").exists()
    assert (workspace_tmp_path / "meeting.summary.md").exists()
    assert focus_path.exists()
    assert cross_reference_calls["count"] == 0
