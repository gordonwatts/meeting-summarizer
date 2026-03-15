from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from typer.testing import CliRunner

from meeting_summarizer import cli
from meeting_summarizer.models import (
    CleanTranscript,
    FocusAreaReview,
    MeetingSummary,
    TranscriptSegment,
)

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


@dataclass
class FakeService:
    clean_result: tuple[CleanTranscript, Path, bool] | None = None
    summary_result: tuple[MeetingSummary, Path, bool] | None = None
    cross_reference_result: tuple[list[FocusAreaReview], Path] | None = None
    full_analysis_calls: list[dict[str, object]] | None = None
    clean_calls: list[dict[str, object]] | None = None
    summary_calls: list[dict[str, object]] | None = None
    cross_reference_calls: list[dict[str, object]] | None = None

    def __post_init__(self) -> None:
        self.full_analysis_calls = self.full_analysis_calls or []
        self.clean_calls = self.clean_calls or []
        self.summary_calls = self.summary_calls or []
        self.cross_reference_calls = self.cross_reference_calls or []

    def clean_transcript(self, transcript_path: str, **kwargs):
        self.clean_calls.append({"transcript_path": transcript_path, **kwargs})
        if self.clean_result is None:
            raise AssertionError("clean_transcript should not be called")
        return self.clean_result

    def summarize_meeting(self, transcript_path: str, **kwargs):
        self.summary_calls.append({"transcript_path": transcript_path, **kwargs})
        if self.summary_result is None:
            raise AssertionError("summarize_meeting should not be called")
        return self.summary_result

    def cross_reference_focus_areas(self, transcript_path: str, **kwargs):
        self.cross_reference_calls.append(
            {"transcript_path": transcript_path, **kwargs}
        )
        if self.cross_reference_result is None:
            raise AssertionError("cross_reference_focus_areas should not be called")
        return self.cross_reference_result

    def run_full_analysis(self, transcript_path: str, **kwargs):
        self.full_analysis_calls.append({"transcript_path": transcript_path, **kwargs})
        return None


def make_cleaned(text: str) -> CleanTranscript:
    return CleanTranscript(
        segments=[TranscriptSegment(speaker="Alice", text=text, start_time="00:00:01")]
    )


def make_summary(paragraph: str) -> MeetingSummary:
    return MeetingSummary(
        paragraph=paragraph,
        themes=[],
        action_items=[],
        resources=[],
        talk_points=[],
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

    service = FakeService()
    monkeypatch.setattr(cli, "_make_service", lambda api_key: service)

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
    assert len(service.full_analysis_calls) == 1


def test_clean_command_passes_max_clean_chars(workspace_tmp_path, monkeypatch) -> None:
    transcript_path = workspace_tmp_path / "meeting.vtt"
    transcript_path.write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nAlice: Hi.\n",
        encoding="utf-8",
    )

    service = FakeService(
        clean_result=(
            make_cleaned("Cleaned sentence."),
            workspace_tmp_path / "meeting.cleaned.md",
            False,
        )
    )
    monkeypatch.setattr(cli, "_make_service", lambda api_key: service)

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
    assert service.clean_calls[0]["max_clean_chars"] == 321


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

    def fail_make_service(*args, **kwargs):
        raise AssertionError(
            "_make_service should not be called when cleaned output already exists"
        )

    monkeypatch.setattr(cli, "_make_service", fail_make_service)

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

    service = FakeService(
        clean_result=(
            make_cleaned("Existing cleaned text."),
            cleaned_path,
            True,
        ),
        summary_result=(
            make_summary("Existing cleaned text."),
            workspace_tmp_path / "meeting.summary.md",
            False,
        ),
    )
    monkeypatch.setattr(cli, "_make_service", lambda api_key: service)

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
    assert service.clean_calls[0]["overwrite"] is False
    assert (
        service.summary_calls[0]["cleaned"].segments[0].text == "Existing cleaned text."
    )


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

    def fail_make_service(*args, **kwargs):
        raise AssertionError(
            "_make_service should not be called when summary output already exists"
        )

    monkeypatch.setattr(cli, "_make_service", fail_make_service)

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

    service = FakeService(
        clean_result=(
            make_cleaned("Fresh cleaned text."),
            workspace_tmp_path / "meeting.cleaned.md",
            False,
        ),
        summary_result=(
            make_summary("Fresh cleaned text."),
            workspace_tmp_path / "meeting.summary.md",
            False,
        ),
    )
    monkeypatch.setattr(cli, "_make_service", lambda api_key: service)

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
    assert service.clean_calls
    assert service.summary_calls


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

    service = FakeService(
        clean_result=(make_cleaned("Existing cleaned text."), cleaned_path, True),
        summary_result=(
            make_summary("Existing summary paragraph."),
            workspace_tmp_path / "meeting.summary.md",
            True,
        ),
        cross_reference_result=([], workspace_tmp_path / "meeting.focus-areas.md"),
    )
    monkeypatch.setattr(cli, "_make_service", lambda api_key: service)

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
    assert (
        service.cross_reference_calls[0]["summary"].paragraph
        == "Existing summary paragraph."
    )
    assert (
        service.cross_reference_calls[0]["cleaned"].segments[0].text
        == "Existing cleaned text."
    )


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

    def fail_make_service(*args, **kwargs):
        raise AssertionError(
            "_make_service should not be called when focus-area output already exists"
        )

    monkeypatch.setattr(cli, "_make_service", fail_make_service)

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

    service = FakeService()
    monkeypatch.setattr(cli, "_make_service", lambda api_key: service)

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
    assert len(service.full_analysis_calls) == 1


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

    def fail_make_service(*args, **kwargs):
        raise AssertionError(
            "_make_service should not be called when all outputs already exist"
        )

    monkeypatch.setattr(cli, "_make_service", fail_make_service)

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

    service = FakeService()
    monkeypatch.setattr(cli, "_make_service", lambda api_key: service)

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
    assert len(service.full_analysis_calls) == 1
