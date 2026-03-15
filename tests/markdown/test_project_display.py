from __future__ import annotations

from pathlib import Path

from rich.console import Console

from meeting_summarizer.markdown.project_display import show_project
from meeting_summarizer.project import load_project


def test_show_project_renders_table(sample_project: Path) -> None:
    project = load_project(sample_project)
    console = Console(record=True, width=100)
    show_project(project, console)
    output = console.export_text()
    assert "Committee" in output
    assert "Tracking" in output
