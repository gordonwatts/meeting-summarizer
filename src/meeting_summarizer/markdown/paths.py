from __future__ import annotations

from pathlib import Path


def derive_output_path(
    transcript_path: str | Path, suffix: str, output_dir: str | Path | None = None
) -> Path:
    source_path = Path(transcript_path)
    directory = Path(output_dir) if output_dir else source_path.parent
    return directory / f"{source_path.stem}{suffix}"
