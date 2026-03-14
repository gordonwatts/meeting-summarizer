from __future__ import annotations

from pathlib import Path
import re

from rich.console import Console
from rich.table import Table

from meeting_summarizer.models import (
    ActionItem,
    CleanTranscript,
    FocusAreaReview,
    MeetingSummary,
    ProjectConfig,
    TalkPoint,
    TranscriptSegment,
)


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


def parse_summary_markdown(content: str) -> MeetingSummary:
    lines = content.splitlines()
    if not lines or lines[0].strip() != "# Meeting Summary":
        raise ValueError("Meeting summary markdown must start with '# Meeting Summary'.")

    section = "paragraph"
    paragraph_lines: list[str] = []
    themes: list[str] = []
    action_items: list[ActionItem] = []
    resources: list[str] = []
    talk_points: list[TalkPoint] = []
    current_talk: TalkPoint | None = None
    talk_subsection: str | None = None

    action_item_pattern = re.compile(r'^- (?P<mentioner>.*?): (?P<description>.*?)(?: Quote: "(?P<quote>.*)")?$')

    def normalize_bullets(items: list[str]) -> list[str]:
        return [] if items == ["None noted."] else items

    def flush_talk() -> None:
        nonlocal current_talk
        if current_talk is None:
            return
        current_talk.salient_points = normalize_bullets(current_talk.salient_points)
        current_talk.questions = normalize_bullets(current_talk.questions)
        current_talk.quotes = normalize_bullets(current_talk.quotes)
        talk_points.append(current_talk)
        current_talk = None

    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "## Themes":
            flush_talk()
            section = "themes"
            continue
        if stripped == "## Action Items":
            flush_talk()
            section = "action_items"
            continue
        if stripped == "## External Resources":
            flush_talk()
            section = "resources"
            continue
        if stripped == "## Talk Highlights":
            flush_talk()
            section = "talk_highlights"
            continue
        if line.startswith("### "):
            flush_talk()
            current_talk = TalkPoint(speaker=line[4:].strip(), salient_points=[], questions=[], quotes=[])
            talk_subsection = None
            continue
        if stripped == "Salient points:":
            talk_subsection = "salient_points"
            continue
        if stripped == "Questions:":
            talk_subsection = "questions"
            continue
        if stripped == "Quotes:":
            talk_subsection = "quotes"
            continue
        if not stripped:
            continue

        if section == "paragraph":
            paragraph_lines.append(line)
            continue
        if section == "themes" and line.startswith("- "):
            themes.append(line[2:])
            continue
        if section == "action_items" and line.startswith("- "):
            if line == "- None noted.":
                continue
            match = action_item_pattern.match(line)
            if match is None:
                raise ValueError("Action item markdown is not in the expected format.")
            action_items.append(
                ActionItem(
                    mentioner=match.group("mentioner"),
                    description=match.group("description"),
                    quote=match.group("quote"),
                )
            )
            continue
        if section == "resources" and line.startswith("- "):
            resources.append(line[2:])
            continue
        if section == "talk_highlights" and current_talk is not None:
            if talk_subsection == "salient_points" and line.startswith("- "):
                current_talk.salient_points.append(line[2:])
                continue
            if talk_subsection == "questions" and line.startswith("- "):
                current_talk.questions.append(line[2:])
                continue
            if talk_subsection == "quotes" and line.startswith('- "') and line.endswith('"'):
                current_talk.quotes.append(line[3:-1])
                continue

    flush_talk()
    return MeetingSummary(
        paragraph="\n".join(paragraph_lines).strip(),
        themes=normalize_bullets(themes),
        action_items=action_items,
        resources=normalize_bullets(resources),
        talk_points=talk_points,
    )


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
