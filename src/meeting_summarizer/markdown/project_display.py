from __future__ import annotations

from rich.console import Console
from rich.table import Table

from meeting_summarizer.models import ProjectConfig


def show_project(project: ProjectConfig, console: Console) -> None:
    """Render a project configuration to a Rich console.

    Args:
        project: Project configuration to display.
        console: Console used for rendering.

    Returns:
        None.
    """
    console.print(f"[bold]{project.name}[/bold]")
    if project.models:
        console.print("Models:")
        for key, value in project.models.items():
            console.print(f"  {key}: {value}")
    table = Table(title="Focus Areas")
    table.add_column("ID")
    table.add_column("Title")
    table.add_column("Description")
    table.add_column("Notes")
    for area in project.focus_areas:
        table.add_row(area.id, area.title, area.description, area.notes or "")
    console.print(table)
