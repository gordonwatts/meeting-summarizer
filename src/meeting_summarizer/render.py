from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.table import Table

from meeting_summarizer.models import (
    ActionItem,
    CleanTranscript,
    ExternalResource,
    FocusAreaReview,
    MeetingSummary,
    ProjectConfig,
    SummaryTheme,
    TalkPoint,
    TranscriptSegment,
)


def derive_output_path(
    transcript_path: str | Path, suffix: str, output_dir: str | Path | None = None
) -> Path:
    source_path = Path(transcript_path)
    directory = Path(output_dir) if output_dir else source_path.parent
    return directory / f"{source_path.stem}{suffix}"


def _escape_table_cell(value: str | None) -> str:
    if not value:
        return ""
    return value.replace("|", "\\|").replace("\n", "<br>")


def _unescape_table_cell(value: str) -> str:
    return value.replace("<br>", "\n").replace("\\|", "|").strip()


def _render_markdown_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    if not rows:
        lines.append(
            "| "
            + " | ".join(
                "None noted." if index == 0 else "" for index, _ in enumerate(headers)
            )
            + " |"
        )
        return lines
    for row in rows:
        lines.append("| " + " | ".join(_escape_table_cell(cell) for cell in row) + " |")
    return lines


def _parse_markdown_table(
    lines: list[str], start_index: int
) -> tuple[list[dict[str, str]], int]:
    header_line = lines[start_index].strip()
    divider_line = lines[start_index + 1].strip()
    if not (header_line.startswith("|") and divider_line.startswith("|")):
        raise ValueError("Expected markdown table.")

    headers = [_unescape_table_cell(cell) for cell in header_line.strip("|").split("|")]
    rows: list[dict[str, str]] = []
    index = start_index + 2
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped.startswith("|"):
            break
        cells = [_unescape_table_cell(cell) for cell in stripped.strip("|").split("|")]
        if len(cells) < len(headers):
            cells.extend([""] * (len(headers) - len(cells)))
        row = dict(zip(headers, cells))
        rows.append(row)
        index += 1
    return rows, index


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
    theme_rows = [[theme.title, "; ".join(theme.details)] for theme in summary.themes]
    lines.extend(_render_markdown_table(["Theme", "Details"], theme_rows))
    lines.extend(["", "## Action Items", ""])
    action_rows = [
        [item.mentioner, item.description, item.quote or ""]
        for item in summary.action_items
    ]
    lines.extend(_render_markdown_table(["Owner", "Action", "Quote"], action_rows))
    lines.extend(["", "## External Resources", ""])
    resource_rows = [
        [resource.name, resource.resource_type or "", resource.context or ""]
        for resource in summary.resources
    ]
    lines.extend(_render_markdown_table(["Resource", "Type", "Context"], resource_rows))
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
        raise ValueError(
            "Meeting summary markdown must start with '# Meeting Summary'."
        )

    section = "paragraph"
    paragraph_lines: list[str] = []
    themes: list[SummaryTheme] = []
    action_items: list[ActionItem] = []
    resources: list[ExternalResource] = []
    talk_points: list[TalkPoint] = []
    current_talk: TalkPoint | None = None
    talk_subsection: str | None = None

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

    index = 1
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if stripped == "## Themes":
            flush_talk()
            section = "themes"
            index += 1
            continue
        if stripped == "## Action Items":
            flush_talk()
            section = "action_items"
            index += 1
            continue
        if stripped == "## External Resources":
            flush_talk()
            section = "resources"
            index += 1
            continue
        if stripped == "## Talk Highlights":
            flush_talk()
            section = "talk_highlights"
            index += 1
            continue
        if line.startswith("### "):
            flush_talk()
            current_talk = TalkPoint(
                speaker=line[4:].strip(), salient_points=[], questions=[], quotes=[]
            )
            talk_subsection = None
            index += 1
            continue
        if stripped == "Salient points:":
            talk_subsection = "salient_points"
            index += 1
            continue
        if stripped == "Questions:":
            talk_subsection = "questions"
            index += 1
            continue
        if stripped == "Quotes:":
            talk_subsection = "quotes"
            index += 1
            continue
        if not stripped:
            index += 1
            continue

        if section == "paragraph":
            paragraph_lines.append(line)
            index += 1
            continue
        if section == "themes" and stripped.startswith("|"):
            rows, index = _parse_markdown_table(lines, index)
            themes = [
                SummaryTheme(
                    title=row.get("Theme", ""),
                    details=normalize_bullets(
                        [
                            item.strip()
                            for item in row.get("Details", "").split(";")
                            if item.strip()
                        ]
                    ),
                )
                for row in rows
                if row.get("Theme", "") != "None noted."
            ]
            continue
        if section == "action_items" and stripped.startswith("|"):
            rows, index = _parse_markdown_table(lines, index)
            action_items = [
                ActionItem(
                    mentioner=row.get("Owner", ""),
                    description=row.get("Action", ""),
                    quote=row.get("Quote") or None,
                )
                for row in rows
                if row.get("Owner", "") != "None noted."
            ]
            continue
        if section == "resources" and stripped.startswith("|"):
            rows, index = _parse_markdown_table(lines, index)
            resources = [
                ExternalResource(
                    name=row.get("Resource", ""),
                    resource_type=row.get("Type") or None,
                    context=row.get("Context") or None,
                )
                for row in rows
                if row.get("Resource", "") != "None noted."
            ]
            continue
        if section == "talk_highlights" and current_talk is not None:
            if talk_subsection == "salient_points" and line.startswith("- "):
                current_talk.salient_points.append(line[2:])
                index += 1
                continue
            if talk_subsection == "questions" and line.startswith("- "):
                current_talk.questions.append(line[2:])
                index += 1
                continue
            if (
                talk_subsection == "quotes"
                and line.startswith('- "')
                and line.endswith('"')
            ):
                current_talk.quotes.append(line[3:-1])
                index += 1
                continue
        index += 1

    flush_talk()
    return MeetingSummary(
        paragraph="\n".join(paragraph_lines).strip(),
        themes=themes,
        action_items=action_items,
        resources=resources,
        talk_points=talk_points,
    )


def render_focus_area_markdown(reviews: list[FocusAreaReview]) -> str:
    lines = ["# Focus Area Cross Reference", ""]
    for review in reviews:
        lines.extend(
            [
                f"## {review.focus_area.title}",
                "",
                review.coverage_note,
                "",
                "Relevant points:",
            ]
        )
        lines.extend(f"- {item}" for item in review.relevant_points or ["None noted."])
        lines.extend(["", "Outstanding questions:"])
        lines.extend(
            f"- {item}" for item in review.outstanding_questions or ["None noted."]
        )
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
