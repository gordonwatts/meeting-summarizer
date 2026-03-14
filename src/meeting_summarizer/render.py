from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.table import Table

from meeting_summarizer.models import CleanTranscript, FocusAreaReview, MeetingSummary, ProjectConfig, TranscriptSegment


def derive_output_path(transcript_path: str | Path, suffix: str, output_dir: str | Path | None = None) -> Path:
    source_path = Path(transcript_path)
    directory = Path(output_dir) if output_dir else source_path.parent
    return directory / f"{source_path.stem}{suffix}"


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
        raise ValueError("Cleaned transcript markdown must start with '# Cleaned Transcript'.")

    segments: list[TranscriptSegment] = []
    current_speaker: str | None = None
    current_start_time: str | None = None
    current_text_lines: list[str] = []

    def flush_segment() -> None:
        nonlocal current_speaker, current_start_time, current_text_lines
        if current_speaker is None:
            return
        text = "\n".join(current_text_lines).strip()
        segments.append(
            TranscriptSegment(
                speaker=current_speaker,
                text=text,
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


def render_summary_markdown(summary: MeetingSummary) -> str:
    lines = ["# Meeting Summary", "", summary.paragraph, "", "## Themes", ""]
    if summary.themes:
        lines.extend(f"- {theme}" for theme in summary.themes)
    else:
        lines.append("- None noted.")
    lines.extend(["", "## Action Items", ""])
    if summary.action_items:
        for item in summary.action_items:
            line = f"- {item.mentioner}: {item.description}"
            if item.quote:
                line += f' Quote: "{item.quote}"'
            lines.append(line)
    else:
        lines.append("- None noted.")
    lines.extend(["", "## External Resources", ""])
    if summary.resources:
        lines.extend(f"- {resource}" for resource in summary.resources)
    else:
        lines.append("- None noted.")
    lines.extend(["", "## Talk Highlights", ""])
    for talk in summary.talk_points:
        lines.extend([f"### {talk.speaker}", "", "Salient points:"])
        lines.extend(f"- {item}" for item in talk.salient_points or ["None noted."])
        lines.extend(["", "Questions:"])
        lines.extend(f"- {item}" for item in talk.questions or ["None noted."])
        if talk.quotes:
            lines.extend(["", "Quotes:"])
            lines.extend(f'- "{quote}"' for quote in talk.quotes)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def render_focus_area_markdown(reviews: list[FocusAreaReview]) -> str:
    lines = ["# Focus Area Cross Reference", ""]
    for review in reviews:
        lines.extend([f"## {review.focus_area.title}", "", review.coverage_note, "", "Relevant points:"])
        lines.extend(f"- {item}" for item in review.relevant_points or ["None noted."])
        lines.extend(["", "Outstanding questions:"])
        lines.extend(f"- {item}" for item in review.outstanding_questions or ["None noted."])
        lines.extend(["", "Action items:"])
        lines.extend(f"- {item}" for item in review.action_items or ["None noted."])
        lines.extend(["", "Quotes:"])
        lines.extend(f'- "{item}"' for item in review.quotes or ["None noted."])
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def show_project(project: ProjectConfig, console: Console) -> None:
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
