from __future__ import annotations

import shutil
from pathlib import Path

import pytest


@pytest.fixture()
def workspace_tmp_path() -> Path:
    root = Path.cwd() / ".test-workdir"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(exist_ok=True)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


@pytest.fixture()
def sample_vtt(workspace_tmp_path: Path) -> Path:
    path = workspace_tmp_path / "meeting.vtt"
    path.write_text(
        "WEBVTT\n\n"
        "00:00:01.000 --> 00:00:03.000\n"
        "Alice: Welcome everyone.\n\n"
        "00:00:03.000 --> 00:00:06.000\n"
        "Alice: Uh let's get started.\n\n"
        "00:00:06.000 --> 00:00:09.000\n"
        "Bob: I posted the slides at example.com.\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture()
def sample_project(workspace_tmp_path: Path) -> Path:
    path = workspace_tmp_path / "project.yaml"
    path.write_text(
        "name: Committee\n"
        "focus_areas:\n"
        "  - id: tracking\n"
        "    title: Tracking\n"
        "    description: Tracking systems and reconstruction.\n",
        encoding="utf-8",
    )
    return path
