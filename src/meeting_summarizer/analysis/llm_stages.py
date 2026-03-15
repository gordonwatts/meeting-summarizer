from __future__ import annotations

import json
import re
from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from meeting_summarizer.models import (
    ActionItem,
    CleanTranscript,
    ExternalResource,
    FocusArea,
    FocusAreaReview,
    MeetingSummary,
    SummaryTheme,
    TalkPoint,
    TranscriptSegment,
)

if TYPE_CHECKING:
    from meeting_summarizer.openai_client import OpenAIClient


def _normalize_model_text(text: str) -> str:
    """Normalize punctuation so persisted markdown stays plain ASCII."""
    return (
        text.replace("â€™", "'")
        .replace("ā€™", "'")
        .replace("â€˜", "'")
        .replace("â€œ", '"')
        .replace("â€�", '"')
        .replace("â€“", "-")
        .replace("â€”", "-")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2026", "...")
    )


def _coerce_text(value: Any) -> str:
    """Convert loosely structured model output into a readable text string."""
    if value is None:
        return ""
    if isinstance(value, str):
        return _normalize_model_text(value).strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        parts = [_coerce_text(item) for item in value]
        return "; ".join(part for part in parts if part)
    if isinstance(value, dict):
        actor = _coerce_text(
            value.get("owner")
            or value.get("mentioner")
            or value.get("speaker")
            or value.get("title")
        )
        quote = _coerce_text(value.get("quote"))
        simple_summary = _coerce_text(value.get("summary"))
        if simple_summary and set(value) == {"summary"}:
            return simple_summary
        if (
            actor
            and quote
            and not any(
                value.get(field)
                for field in (
                    "task",
                    "description",
                    "text",
                    "summary",
                    "note",
                    "coverage_note",
                )
            )
        ):
            return f'{actor}: "{quote}"'
        main_text = _coerce_text(
            value.get("task")
            or value.get("description")
            or value.get("text")
            or value.get("summary")
            or value.get("note")
            or value.get("coverage_note")
        )
        if actor and main_text:
            line = f"{actor}: {main_text}"
        else:
            ordered_parts = [
                f"{key.replace('_', ' ')}: {_coerce_text(item)}"
                for key, item in value.items()
                if _coerce_text(item)
            ]
            line = "; ".join(ordered_parts)
        if quote:
            return f'{line} Quote: "{quote}"' if line else quote
        return line
    return str(value)


def _coerce_text_list(values: Any) -> list[str]:
    """Normalize model output into a list of non-empty text strings."""
    if not isinstance(values, list):
        text = _coerce_text(values)
        return [text] if text else []
    items = [_coerce_text(value) for value in values]
    return [item for item in items if item]


def _coerce_string_field(value: Any) -> str | None:
    """Normalize an optional scalar field from model output."""
    text = _coerce_text(value)
    return text or None


def _parse_structured_text_fields(text: str) -> dict[str, str]:
    """Parse semicolon-delimited key/value pairs from loose model text."""
    fields: dict[str, str] = {}
    for part in text.split(";"):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key and value:
            fields[key] = value
    return fields


def _strip_leading_label(text: str, labels: tuple[str, ...]) -> str:
    """Remove a leading label such as 'point:' or 'question:' from a string."""
    lowered = text.lower()
    for label in labels:
        prefix = f"{label}:"
        if lowered.startswith(prefix):
            return text[len(prefix) :].strip()
    return text


def _compose_person_scoped_line(
    person: str | None, content: str | None, *, allow_person_only: bool = False
) -> str:
    """Combine an optional person name with content."""
    clean_content = _coerce_text(content)
    clean_person = _coerce_text(person)
    if clean_person and clean_content:
        return f"{clean_person}: {clean_content}"
    if clean_content:
        return clean_content
    return clean_person if allow_person_only else ""


def _coerce_focus_relevant_point(value: Any) -> str:
    """Normalize a focus-area relevant point into a short person-scoped line."""
    if isinstance(value, dict):
        return _compose_person_scoped_line(
            value.get("speaker") or value.get("mentioner") or value.get("owner"),
            value.get("point")
            or value.get("relevant_point")
            or value.get("text")
            or value.get("description")
            or value.get("summary")
            or value.get("note"),
        )

    text = _coerce_text(value)
    fields = _parse_structured_text_fields(text)
    if fields:
        return _compose_person_scoped_line(
            fields.get("speaker") or fields.get("mentioner") or fields.get("owner"),
            fields.get("point")
            or fields.get("relevant point")
            or fields.get("text")
            or fields.get("description")
            or fields.get("summary")
            or fields.get("note"),
        )
    return _strip_leading_label(text, ("point", "relevant point"))


def _coerce_focus_question(value: Any) -> str:
    """Normalize a focus-area outstanding question into a short line."""
    if isinstance(value, dict):
        return _compose_person_scoped_line(
            value.get("speaker") or value.get("mentioner") or value.get("owner"),
            value.get("question")
            or value.get("outstanding_question")
            or value.get("text")
            or value.get("description")
            or value.get("summary")
            or value.get("note"),
        )

    text = _coerce_text(value)
    fields = _parse_structured_text_fields(text)
    if fields:
        return _compose_person_scoped_line(
            fields.get("speaker") or fields.get("mentioner") or fields.get("owner"),
            fields.get("question")
            or fields.get("outstanding question")
            or fields.get("text")
            or fields.get("description")
            or fields.get("summary")
            or fields.get("note"),
        )
    return _strip_leading_label(text, ("question", "outstanding question"))


def _coerce_focus_action_item(value: Any) -> str:
    """Normalize a focus-area action item into a concise owner-scoped line."""
    if isinstance(value, dict):
        return _compose_person_scoped_line(
            value.get("assigned_to")
            or value.get("owner")
            or value.get("mentioner")
            or value.get("speaker"),
            value.get("action")
            or value.get("task")
            or value.get("description")
            or value.get("text")
            or value.get("summary")
            or value.get("note"),
        )

    text = _coerce_text(value)
    fields = _parse_structured_text_fields(text)
    if fields:
        return _compose_person_scoped_line(
            fields.get("assigned to")
            or fields.get("owner")
            or fields.get("mentioner")
            or fields.get("speaker"),
            fields.get("action")
            or fields.get("task")
            or fields.get("description")
            or fields.get("text")
            or fields.get("summary")
            or fields.get("note"),
        )
    return _strip_leading_label(text, ("action", "task"))


def _derive_mentioned_people(*groups: list[str]) -> list[str]:
    """Extract a stable ordered list of person names from prefixed lines."""
    seen: set[str] = set()
    people: list[str] = []
    for group in groups:
        for item in group:
            match = re.match(r"^([^:]+):\s+.+$", item)
            if not match:
                continue
            candidate = match.group(1).strip()
            if candidate in seen:
                continue
            seen.add(candidate)
            people.append(candidate)
    return people


def _limit_focus_items(items: list[str], max_items: int = 4) -> list[str]:
    """Keep the highest-priority focus-area items concise by truncating the list."""
    return items[:max_items]


def _coerce_theme(value: Any) -> SummaryTheme:
    """Normalize a model-produced theme into the summary theme schema."""
    if isinstance(value, dict):
        title = _coerce_text(
            value.get("theme")
            or value.get("topic")
            or value.get("title")
            or value.get("name")
        )
        details = _coerce_text_list(
            value.get("details") or value.get("notes") or value.get("points") or []
        )
        if not title:
            title = _coerce_text(value)
            details = []
        return SummaryTheme(title=title or "Untitled theme", details=details)
    return SummaryTheme(title=_coerce_text(value) or "Untitled theme", details=[])


def _coerce_resource(value: Any) -> ExternalResource:
    """Normalize a model-produced resource into the resource schema."""
    if isinstance(value, dict):
        return ExternalResource(
            name=_coerce_text(
                value.get("name") or value.get("title") or value.get("resource")
            )
            or "Unnamed resource",
            resource_type=_coerce_string_field(
                value.get("type") or value.get("resource_type")
            ),
            context=_coerce_string_field(
                value.get("context") or value.get("description") or value.get("notes")
            ),
        )
    return ExternalResource(name=_coerce_text(value) or "Unnamed resource")


def transcript_to_text(segments: list[TranscriptSegment]) -> str:
    """Render transcript segments into the text format used in prompts.

    Args:
        segments: Transcript segments to serialize.

    Returns:
        A newline-delimited transcript string.
    """
    lines: list[str] = []
    for segment in segments:
        prefix = segment.speaker
        if segment.start_time:
            prefix = f"{prefix} [{segment.start_time}]"
        lines.append(f"{prefix}: {segment.text}")
    return "\n".join(lines)


def clean_transcript_with_llm(
    client: OpenAIClient, model: str, segments: list[TranscriptSegment]
) -> CleanTranscript:
    """Run the transcript cleaning stage against the shared OpenAI client.

    Args:
        client: Shared OpenAI client wrapper.
        model: Model name for the cleaning stage.
        segments: Transcript segments to clean.

    Returns:
        The cleaned transcript.
    """
    payload = client.generate_json(
        model=model,
        instructions=(
            "Rewrite the transcript to remove filler words, false starts, and operational chatter "
            "that is not substantive. Drop brief acknowledgments, mic and recording logistics, "
            "room setup chatter, scheduling side comments, greetings, transitions into the meeting, "
            "and other administrative exchange unless they materially affect the substance of the "
            "discussion. Preserve meaning for substantive content and keep full sentences. Do not "
            "summarize, paraphrase away decisions, or invent content. Return JSON with a 'segments' "
            "array. Each segment must include speaker, text, start_time, end_time, and source_lineage."
        ),
        input_text=transcript_to_text(segments),
    )
    return CleanTranscript(
        segments=[
            TranscriptSegment(
                speaker=item["speaker"],
                text=item["text"],
                start_time=item.get("start_time"),
                end_time=item.get("end_time"),
                source_lineage=item.get("source_lineage", []),
            )
            for item in payload["segments"]
        ]
    )


def summarize_meeting_with_llm(
    client: OpenAIClient, model: str, cleaned: CleanTranscript
) -> MeetingSummary:
    """Run the meeting summarization stage against the shared OpenAI client.

    Args:
        client: Shared OpenAI client wrapper.
        model: Model name for the summarization stage.
        cleaned: Cleaned transcript content.

    Returns:
        The structured meeting summary.
    """
    payload = client.generate_json(
        model=model,
        instructions=(
            "Analyze the cleaned meeting transcript. Return JSON with keys: paragraph, themes, "
            "action_items, resources, talk_points. The paragraph must be one paragraph. Include "
            "themes as short plain-English topic labels only, with no descriptions or nested detail "
            "items. Deduplicate overlapping themes, action items, and resources. Include only concrete "
            "action items with mentioner, description, and quote when available. Include resources with "
            "name, type, and context when available. For each talk point include speaker, "
            "salient_points, questions, and direct quotes wherever possible."
        ),
        input_text=transcript_to_text(cleaned.segments),
    )
    return MeetingSummary(
        paragraph=_coerce_text(payload.get("paragraph")) or "No summary provided.",
        themes=[_coerce_theme(item) for item in payload.get("themes", [])],
        action_items=[
            ActionItem(
                mentioner=_coerce_text(
                    item.get("mentioner") if isinstance(item, dict) else None
                )
                or _coerce_text(item.get("owner") if isinstance(item, dict) else None)
                or "Unknown",
                description=_coerce_text(
                    item.get("description") if isinstance(item, dict) else item
                )
                or "No action recorded.",
                quote=_coerce_string_field(
                    item.get("quote") if isinstance(item, dict) else None
                ),
            )
            for item in payload.get("action_items", [])
        ],
        resources=[_coerce_resource(item) for item in payload.get("resources", [])],
        talk_points=[
            TalkPoint(
                speaker=_coerce_text(item.get("speaker")) or "Unknown",
                salient_points=_coerce_text_list(item.get("salient_points", [])),
                questions=_coerce_text_list(item.get("questions", [])),
                quotes=_coerce_text_list(item.get("quotes", [])),
            )
            for item in payload.get("talk_points", [])
        ],
    )


def cross_reference_with_llm(
    client: OpenAIClient,
    model: str,
    summary: MeetingSummary,
    cleaned: CleanTranscript,
    focus_area: FocusArea,
) -> FocusAreaReview:
    """Run focus-area cross-reference analysis for a single focus area.

    Args:
        client: Shared OpenAI client wrapper.
        model: Model name for the cross-reference stage.
        summary: Structured meeting summary.
        cleaned: Cleaned transcript content.
        focus_area: Focus area to review.

    Returns:
        The focus-area review.
    """
    payload = client.generate_json(
        model=model,
        instructions=(
            "Cross-reference the provided focus area against the meeting summary and cleaned transcript. "
            "Return JSON with keys: mentioned_people, relevant_points, outstanding_questions, "
            "action_items, quotes, coverage_note. Keep this concise. Include only materially relevant "
            "points that are specific to the focus area; ignore passing mentions, category examples, "
            "and generic statements that could apply equally to any focus area. Each relevant point "
            "should be a short sentence and should stay tied to the speaker when possible. Return at "
            "most 4 relevant points, 4 outstanding questions, and 4 action items. Keep outstanding "
            "questions short. Keep action items terse and concrete. Quotes may be empty. Coverage_note "
            "should be brief because it may be omitted from the final rendering."
        ),
        input_text=json.dumps(
            {
                "summary": asdict(summary),
                "focus_area": asdict(focus_area),
                "cleaned_transcript": transcript_to_text(cleaned.segments),
            },
            ensure_ascii=True,
        ),
    )
    relevant_points = _limit_focus_items([
        item
        for item in (_coerce_focus_relevant_point(value) for value in payload.get("relevant_points", []))
        if item
    ])
    outstanding_questions = _limit_focus_items([
        item
        for item in (_coerce_focus_question(value) for value in payload.get("outstanding_questions", []))
        if item
    ])
    action_items = _limit_focus_items([
        item
        for item in (_coerce_focus_action_item(value) for value in payload.get("action_items", []))
        if item
    ])
    mentioned_people = _coerce_text_list(payload.get("mentioned_people", []))
    if not mentioned_people:
        mentioned_people = _derive_mentioned_people(
            relevant_points, outstanding_questions, action_items
        )
    return FocusAreaReview(
        focus_area=focus_area,
        mentioned_people=mentioned_people,
        relevant_points=relevant_points,
        outstanding_questions=outstanding_questions,
        action_items=action_items,
        quotes=_coerce_text_list(payload.get("quotes", [])),
        coverage_note=_coerce_text(payload.get("coverage_note"))
        or "No coverage note provided.",
    )
