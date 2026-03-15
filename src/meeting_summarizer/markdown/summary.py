from __future__ import annotations

from meeting_summarizer.markdown.common import (
    parse_markdown_table,
    render_markdown_table,
)
from meeting_summarizer.models import (
    ActionItem,
    ExternalResource,
    MeetingSummary,
    SummaryTheme,
    TalkPoint,
)


def render_summary_markdown(summary: MeetingSummary) -> str:
    """Render a meeting summary as markdown.

    Args:
        summary: Structured meeting summary to serialize.

    Returns:
        Markdown content for the meeting summary.
    """
    lines = ["# Meeting Summary", "", summary.paragraph, "", "## Themes", ""]
    lines.extend(f"- {theme.title}" for theme in summary.themes or [SummaryTheme("None noted.")])
    lines.extend(["", "## Action Items", ""])
    action_rows = [
        [item.mentioner, item.description, item.quote or ""]
        for item in summary.action_items
    ]
    lines.extend(render_markdown_table(["Owner", "Action", "Quote"], action_rows))
    lines.extend(["", "## External Resources", ""])
    resource_rows = [
        [resource.name, resource.resource_type or "", resource.context or ""]
        for resource in summary.resources
    ]
    lines.extend(render_markdown_table(["Resource", "Type", "Context"], resource_rows))
    lines.extend(["", "## Talk Highlights", ""])
    for talk in summary.talk_points:
        lines.extend([f"### {talk.speaker}", "", "Salient points:"])
        lines.extend(f"- {item}" for item in talk.salient_points or ["None noted."])
        if talk.questions:
            lines.extend(["", "Questions:"])
            lines.extend(f"- {item}" for item in talk.questions)
        if talk.quotes:
            lines.extend(["", "Quotes:"])
            lines.extend(f'- "{quote}"' for quote in talk.quotes)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def parse_summary_markdown(content: str) -> MeetingSummary:
    """Parse meeting summary markdown back into the domain model.

    Args:
        content: Markdown content to parse.

    Returns:
        The parsed meeting summary.
    """
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
        """Collapse placeholder bullets into an empty list."""
        return [] if items == ["None noted."] else items

    def flush_talk() -> None:
        """Append the current talk-point buffer to the parsed result."""
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
            rows, index = parse_markdown_table(lines, index)
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
        if section == "themes" and line.startswith("- "):
            themes.append(SummaryTheme(title=line[2:].strip()))
            index += 1
            continue
        if section == "action_items" and stripped.startswith("|"):
            rows, index = parse_markdown_table(lines, index)
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
            rows, index = parse_markdown_table(lines, index)
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
