from __future__ import annotations

from meeting_summarizer.models import CleanTranscript, TranscriptSegment


def render_cleaned_markdown(cleaned: CleanTranscript) -> str:
    lines = ["# Cleaned Transcript", ""]
    for segment in cleaned.segments:
        heading = f"## {segment.speaker}"
        if segment.start_time:
            heading += f" ({segment.start_time})"
        lines.extend([heading, "", segment.text, ""])
    return "\n".join(lines).strip() + "\n"


def parse_cleaned_markdown(content: str) -> CleanTranscript:
    lines = content.splitlines()
    if not lines or lines[0].strip() != "# Cleaned Transcript":
        raise ValueError(
            "Cleaned transcript markdown must start with '# Cleaned Transcript'."
        )

    segments: list[TranscriptSegment] = []
    current_speaker: str | None = None
    current_start_time: str | None = None
    current_text_lines: list[str] = []

    def flush_segment() -> None:
        nonlocal current_speaker, current_start_time, current_text_lines
        if current_speaker is None:
            return
        segments.append(
            TranscriptSegment(
                speaker=current_speaker,
                text="\n".join(current_text_lines).strip(),
                start_time=current_start_time,
            )
        )
        current_speaker = None
        current_start_time = None
        current_text_lines = []

    for line in lines[1:]:
        if line.startswith("## "):
            flush_segment()
            heading = line[3:].strip()
            if heading.endswith(")") and " (" in heading:
                speaker, start_time = heading.rsplit(" (", 1)
                current_speaker = speaker
                current_start_time = start_time[:-1]
            else:
                current_speaker = heading
                current_start_time = None
            continue
        if current_speaker is not None:
            current_text_lines.append(line)

    flush_segment()
    return CleanTranscript(segments=segments)
