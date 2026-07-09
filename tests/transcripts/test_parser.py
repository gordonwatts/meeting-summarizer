from __future__ import annotations

from meeting_summarizer.transcripts.parser import parse_transcript


def test_parse_vtt_merges_adjacent_speaker_turns(sample_vtt) -> None:
    segments = parse_transcript(sample_vtt)
    assert len(segments) == 2
    assert segments[0].speaker == "Alice"
    assert "Welcome everyone." in segments[0].text
    assert "Uh let's get started." in segments[0].text


def test_parse_vtt_accepts_windows_line_endings(workspace_tmp_path) -> None:
    path = workspace_tmp_path / "meeting.vtt"
    path.write_bytes(
        b"WEBVTT\r\n"
        b"\r\n"
        b"00:00:01.000 --> 00:00:02.000\r\n"
        b"Alice: Welcome everyone.\r\n"
    )

    segments = parse_transcript(path)

    assert len(segments) == 1
    assert segments[0].speaker == "Alice"
    assert segments[0].text == "Welcome everyone."


def test_parse_vtt_accepts_webvtt_voice_cues(workspace_tmp_path) -> None:
    path = workspace_tmp_path / "meeting.vtt"
    path.write_text(
        "WEBVTT\n\n"
        "00:00:01.000 --> 00:00:02.000\n"
        "<v Alice> Welcome everyone.\n",
        encoding="utf-8",
    )

    segments = parse_transcript(path)

    assert len(segments) == 1
    assert segments[0].speaker == "Alice"
    assert segments[0].text == "Welcome everyone."


def test_parse_vtt_preserves_speakerless_cues(workspace_tmp_path) -> None:
    path = workspace_tmp_path / "meeting.vtt"
    path.write_text(
        "WEBVTT\n\n"
        "00:00:01.000 --> 00:00:02.000\n"
        "First sentence.\n\n"
        "00:00:03.000 --> 00:00:04.000\n"
        "Second sentence.\n",
        encoding="utf-8",
    )

    segments = parse_transcript(path)

    assert len(segments) == 2
    assert [segment.speaker for segment in segments] == ["Unknown", "Unknown"]
    assert [segment.text for segment in segments] == [
        "First sentence.",
        "Second sentence.",
    ]


def test_parse_txt_appends_continuation_lines(workspace_tmp_path) -> None:
    path = workspace_tmp_path / "meeting.txt"
    path.write_text(
        "00:00:01 Alice: First line\n" "continued thought\n" "00:00:04 Bob: Reply\n",
        encoding="utf-8",
    )
    segments = parse_transcript(path)
    assert len(segments) == 2
    assert "continued thought" in segments[0].text


def test_parse_zoom_txt_blocks(workspace_tmp_path) -> None:
    path = workspace_tmp_path / "meeting.txt"
    path.write_text(
        "[Alice] 00:00:01\n"
        "First line.\n"
        "\n"
        "[Bob] 00:00:04\n"
        "Reply line one.\n"
        "Reply line two.\n",
        encoding="utf-8",
    )
    segments = parse_transcript(path)
    assert len(segments) == 2
    assert segments[0].speaker == "Alice"
    assert segments[0].start_time == "00:00:01"
    assert segments[1].text == "Reply line one. Reply line two."
