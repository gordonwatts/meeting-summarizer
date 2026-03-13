from __future__ import annotations

import logging
import re
from pathlib import Path

from meeting_summarizer.models import TranscriptSegment

LOGGER = logging.getLogger(__name__)

TIME_RANGE_RE = re.compile(
    r"^(?P<start>\d{2}:\d{2}:\d{2}\.\d{3}) --> (?P<end>\d{2}:\d{2}:\d{2}\.\d{3})$"
)
VTT_SPEAKER_RE = re.compile(r"^(?P<speaker>[^:]+):\s*(?P<text>.+)$")
TXT_LINE_RE = re.compile(
    r"^(?P<time>\d{1,2}:\d{2}:\d{2})(?:\s+)?(?P<speaker>[^:]+):\s*(?P<text>.+)$"
)


def parse_transcript(path: str | Path) -> list[TranscriptSegment]:
    transcript_path = Path(path)
    raw_text = transcript_path.read_text(encoding="utf-8")
    if transcript_path.suffix.lower() == ".vtt":
        return _merge_adjacent_segments(_parse_vtt(raw_text))
    if transcript_path.suffix.lower() == ".txt":
        return _merge_adjacent_segments(_parse_zoom_text(raw_text))
    raise ValueError(f"Unsupported transcript format: {transcript_path.suffix}")


def _parse_vtt(raw_text: str) -> list[TranscriptSegment]:
    blocks = [block.strip() for block in raw_text.split("\n\n") if block.strip()]
    segments: list[TranscriptSegment] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines or lines[0] == "WEBVTT":
            continue
        time_index = 0
        if not TIME_RANGE_RE.match(lines[0]) and len(lines) > 1:
            time_index = 1
        match = TIME_RANGE_RE.match(lines[time_index])
        if not match:
            continue
        text_lines = lines[time_index + 1 :]
        if not text_lines:
            continue
        speaker_match = VTT_SPEAKER_RE.match(" ".join(text_lines))
        if not speaker_match:
            continue
        segments.append(
            TranscriptSegment(
                speaker=speaker_match.group("speaker").strip(),
                text=speaker_match.group("text").strip(),
                start_time=match.group("start"),
                end_time=match.group("end"),
                source_lineage=text_lines,
            )
        )
    return segments


def _parse_zoom_text(raw_text: str) -> list[TranscriptSegment]:
    segments: list[TranscriptSegment] = []
    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = TXT_LINE_RE.match(stripped)
        if match:
            segments.append(
                TranscriptSegment(
                    speaker=match.group("speaker").strip(),
                    text=match.group("text").strip(),
                    start_time=match.group("time"),
                    source_lineage=[stripped],
                )
            )
            continue
        if segments:
            segments[-1].text = f"{segments[-1].text} {stripped}".strip()
            segments[-1].source_lineage.append(stripped)
    return segments


def _merge_adjacent_segments(segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
    if not segments:
        return []
    merged = [segments[0]]
    for segment in segments[1:]:
        current = merged[-1]
        if current.speaker == segment.speaker:
            current.text = f"{current.text} {segment.text}".strip()
            current.end_time = segment.end_time or current.end_time
            current.source_lineage.extend(segment.source_lineage)
        else:
            merged.append(segment)
    LOGGER.debug("Parsed %d merged segments", len(merged))
    return merged
