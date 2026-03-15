from __future__ import annotations

from pathlib import Path


def derive_output_path(
    transcript_path: str | Path, suffix: str, output_dir: str | Path | None = None
) -> Path:
    """Derive the output file path for a transcript artifact.

    Args:
        transcript_path: Source transcript path.
        suffix: Output suffix such as `.summary.md`.
        output_dir: Optional directory override for the generated artifact.

    Returns:
        The resolved output path.
    """
    source_path = Path(transcript_path)
    directory = Path(output_dir) if output_dir else source_path.parent
    return directory / f"{source_path.stem}{suffix}"
