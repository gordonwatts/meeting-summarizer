from __future__ import annotations

from meeting_summarizer.markdown.paths import derive_output_path


def test_derive_output_path_uses_sibling_file(workspace_tmp_path) -> None:
    transcript = workspace_tmp_path / "meeting.vtt"
    assert (
        derive_output_path(transcript, ".summary.md")
        == workspace_tmp_path / "meeting.summary.md"
    )
