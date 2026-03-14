from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml

from meeting_summarizer.models import FocusArea, ProjectConfig

LOGGER = logging.getLogger(__name__)


def resolve_project_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.suffix:
        return candidate
    return candidate.with_suffix(".yaml")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "focus-area"


def load_project(path: str | Path) -> ProjectConfig:
    resolved = resolve_project_path(path)
    data = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
    focus_areas = [
        FocusArea(
            id=item["id"],
            title=item["title"],
            description=item["description"],
            notes=item.get("notes"),
        )
        for item in data.get("focus_areas", [])
    ]
    return ProjectConfig(
        name=data["name"],
        focus_areas=focus_areas,
        models=data.get("models", {}),
        path=resolved,
    )


def save_project(project: ProjectConfig, path: str | Path | None = None) -> Path:
    resolved = resolve_project_path(path or project.path or "project.yaml")
    payload: dict[str, object] = {
        "name": project.name,
        "focus_areas": [
            {
                "id": area.id,
                "title": area.title,
                "description": area.description,
                **({"notes": area.notes} if area.notes else {}),
            }
            for area in project.focus_areas
        ],
    }
    if project.models:
        payload["models"] = project.models
    resolved.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    LOGGER.info(f"Saved project to {resolved}")
    project.path = resolved
    return resolved


def init_project(path: str | Path, name: str) -> ProjectConfig:
    project = ProjectConfig(name=name, focus_areas=[], path=resolve_project_path(path))
    save_project(project, project.path)
    return project


def add_focus_area(path: str | Path, title: str, description: str, notes: str | None = None) -> FocusArea:
    project = load_project(path)
    area = FocusArea(id=slugify(title), title=title, description=description, notes=notes)
    project.focus_areas.append(area)
    save_project(project, project.path)
    return area
