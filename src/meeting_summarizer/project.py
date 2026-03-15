from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import yaml

from meeting_summarizer.models import FocusArea, ProjectConfig

LOGGER = logging.getLogger(__name__)


def resolve_project_path(path: str | Path) -> Path:
    """Resolve a project path, adding a `.yaml` suffix when none is provided.

    Args:
        path: User-provided project path.

    Returns:
        The normalized project file path.
    """
    candidate = Path(path)
    if candidate.suffix:
        return candidate
    return candidate.with_suffix(".yaml")


def slugify(value: str) -> str:
    """Create a stable focus-area identifier from a title string."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "focus-area"


def _require_mapping(data: Any, *, context: str) -> dict[str, Any]:
    """Validate that the supplied value is a mapping."""
    if not isinstance(data, dict):
        raise ValueError(f"{context} must be a mapping.")
    return data


def _require_string(value: Any, *, field_name: str) -> str:
    """Validate that the supplied value is a non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _validate_focus_areas(data: Any) -> list[FocusArea]:
    """Validate and normalize focus-area entries from project YAML."""
    if data is None:
        return []
    if not isinstance(data, list):
        raise ValueError("focus_areas must be a list.")

    focus_areas: list[FocusArea] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(data):
        area_data = _require_mapping(item, context=f"focus_areas[{index}]")
        area = FocusArea(
            id=_require_string(area_data.get("id"), field_name=f"focus_areas[{index}].id"),
            title=_require_string(
                area_data.get("title"), field_name=f"focus_areas[{index}].title"
            ),
            description=_require_string(
                area_data.get("description"),
                field_name=f"focus_areas[{index}].description",
            ),
            notes=(
                _require_string(
                    area_data.get("notes"), field_name=f"focus_areas[{index}].notes"
                )
                if area_data.get("notes") is not None
                else None
            ),
        )
        if area.id in seen_ids:
            raise ValueError(f"Duplicate focus area id: {area.id}")
        seen_ids.add(area.id)
        focus_areas.append(area)
    return focus_areas


def _validate_models(data: Any) -> dict[str, str]:
    """Validate the optional model override mapping from project YAML."""
    if data is None:
        return {}
    models = _require_mapping(data, context="models")
    return {
        _require_string(key, field_name="models key"): _require_string(
            value, field_name=f"models.{key}"
        )
        for key, value in models.items()
    }


def load_project(path: str | Path) -> ProjectConfig:
    """Load and validate a project configuration from YAML.

    Args:
        path: Path to the project file or stem without an extension.

    Returns:
        The validated project configuration.
    """
    resolved = resolve_project_path(path)
    data = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
    project_data = _require_mapping(data, context="project")
    return ProjectConfig(
        name=_require_string(project_data.get("name"), field_name="name"),
        focus_areas=_validate_focus_areas(project_data.get("focus_areas")),
        models=_validate_models(project_data.get("models")),
        path=resolved,
    )


def save_project(project: ProjectConfig, path: str | Path | None = None) -> Path:
    """Serialize a project configuration back to YAML.

    Args:
        project: Project configuration to save.
        path: Optional output path override.

    Returns:
        The path that was written.
    """
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
    """Create and persist a new empty project configuration.

    Args:
        path: Destination path for the project file.
        name: Human-readable project name.

    Returns:
        The created project configuration.
    """
    project = ProjectConfig(name=name, focus_areas=[], path=resolve_project_path(path))
    save_project(project, project.path)
    return project


def add_focus_area(
    path: str | Path, title: str, description: str, notes: str | None = None
) -> FocusArea:
    """Append a new focus area to an existing project file.

    Args:
        path: Project file to update.
        title: Focus-area title.
        description: Focus-area description.
        notes: Optional extra notes for the focus area.

    Returns:
        The added focus area.
    """
    project = load_project(path)
    area_id = slugify(title)
    if any(existing.id == area_id for existing in project.focus_areas):
        raise ValueError(f"Focus area id already exists: {area_id}")
    area = FocusArea(id=area_id, title=title, description=description, notes=notes)
    project.focus_areas.append(area)
    save_project(project, project.path)
    return area
