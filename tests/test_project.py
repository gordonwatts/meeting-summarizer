from __future__ import annotations

from pathlib import Path

from rich.console import Console

from meeting_summarizer.project import add_focus_area, init_project, load_project, resolve_project_path
from meeting_summarizer.render import show_project


def test_resolve_project_path_adds_yaml_suffix() -> None:
    assert resolve_project_path("project") == Path("project.yaml")


def test_init_and_add_focus_area(workspace_tmp_path) -> None:
    project_path = workspace_tmp_path / "project"
    init_project(project_path, "Committee")
    area = add_focus_area(project_path, "Trigger Systems", "Latency-sensitive ML.")
    project = load_project(project_path)
    assert project.path == workspace_tmp_path / "project.yaml"
    assert area.id == "trigger-systems"
    assert project.focus_areas[0].title == "Trigger Systems"


def test_show_project_renders_table(sample_project: Path) -> None:
    project = load_project(sample_project)
    console = Console(record=True, width=100)
    show_project(project, console)
    output = console.export_text()
    assert "Committee" in output
    assert "Tracking" in output
