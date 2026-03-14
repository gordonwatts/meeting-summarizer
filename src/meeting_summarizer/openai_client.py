from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from openai import OpenAI

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

LOGGER = logging.getLogger(__name__)


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        parts = [_coerce_text(item) for item in value]
        return "; ".join(part for part in parts if part)
    if isinstance(value, dict):
        actor = _coerce_text(value.get("owner") or value.get("mentioner") or value.get("speaker") or value.get("title"))
        quote = _coerce_text(value.get("quote"))
        simple_summary = _coerce_text(value.get("summary"))
        if simple_summary and set(value) == {"summary"}:
            return simple_summary
        if actor and quote and not any(
            value.get(field) for field in ("task", "description", "text", "summary", "note", "coverage_note")
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
    if not isinstance(values, list):
        text = _coerce_text(values)
        return [text] if text else []
    items = [_coerce_text(value) for value in values]
    return [item for item in items if item]


def _coerce_string_field(value: Any) -> str | None:
    text = _coerce_text(value)
    return text or None


def _coerce_theme(value: Any) -> SummaryTheme:
    if isinstance(value, dict):
        title = _coerce_text(value.get("theme") or value.get("topic") or value.get("title") or value.get("name"))
        details = _coerce_text_list(value.get("details") or value.get("notes") or value.get("points") or [])
        if not title:
            title = _coerce_text(value)
            details = []
        return SummaryTheme(title=title or "Untitled theme", details=details)
    return SummaryTheme(title=_coerce_text(value) or "Untitled theme", details=[])


def _coerce_resource(value: Any) -> ExternalResource:
    if isinstance(value, dict):
        return ExternalResource(
            name=_coerce_text(value.get("name") or value.get("title") or value.get("resource")) or "Unnamed resource",
            resource_type=_coerce_string_field(value.get("type") or value.get("resource_type")),
            context=_coerce_string_field(value.get("context") or value.get("description") or value.get("notes")),
        )
    return ExternalResource(name=_coerce_text(value) or "Unnamed resource")


def _default_cache_dir() -> Path:
    return Path(__file__).resolve().parents[2] / ".cache" / "meeting-summarizer"


class OpenAIClient:
    def __init__(self, api_key: str, cache_dir: Path | None = None):
        self._client = OpenAI(api_key=api_key)
        self._cache_dir = cache_dir or _default_cache_dir()

    def _cache_path(self, *, model: str, instructions: str, input_text: str) -> Path:
        payload = json.dumps(
            {
                "model": model,
                "instructions": instructions,
                "input_text": input_text,
                "response_format": {"type": "json_object"},
            },
            ensure_ascii=True,
            sort_keys=True,
        ).encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()
        return self._cache_dir / f"{digest}.json"

    def _read_cached_response(self, cache_path: Path) -> dict[str, Any] | None:
        if not cache_path.exists():
            return None
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            LOGGER.warning("Ignoring unreadable cache entry at %s", cache_path)
            return None
        if not isinstance(cached, dict) or "payload" not in cached or not isinstance(cached["payload"], dict):
            LOGGER.warning("Ignoring invalid cache entry at %s", cache_path)
            return None
        LOGGER.debug("OpenAI cache hit model=%s path=%s", cached.get("model", "unknown"), cache_path)
        return cached["payload"]

    def _write_cached_response(self, cache_path: Path, *, model: str, payload: dict[str, Any]) -> None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        record = {"model": model, "payload": payload}
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=cache_path.parent,
            delete=False,
            suffix=".tmp",
        ) as handle:
            json.dump(record, handle, ensure_ascii=True, sort_keys=True)
            handle.write("\n")
            temp_path = Path(handle.name)
        os.replace(temp_path, cache_path)

    def generate_json(self, *, model: str, instructions: str, input_text: str) -> dict[str, Any]:
        if not input_text.strip():
            raise ValueError("OpenAI input_text cannot be empty.")
        cache_path = self._cache_path(model=model, instructions=instructions, input_text=input_text)
        cached_payload = self._read_cached_response(cache_path)
        if cached_payload is not None:
            return cached_payload
        LOGGER.debug("Calling OpenAI model=%s", model)
        response = self._client.responses.create(
            model=model,
            instructions=instructions,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": f"Respond with JSON only.\n\n{input_text}",
                        }
                    ],
                }
            ],
            text={"format": {"type": "json_object"}},
        )
        output_text = getattr(response, "output_text", None)
        if not output_text:
            raise ValueError("OpenAI response did not contain output_text.")
        payload = json.loads(output_text)
        self._write_cached_response(cache_path, model=model, payload=payload)
        return payload


def transcript_to_text(segments: list[TranscriptSegment]) -> str:
    lines: list[str] = []
    for segment in segments:
        prefix = segment.speaker
        if segment.start_time:
            prefix = f"{prefix} [{segment.start_time}]"
        lines.append(f"{prefix}: {segment.text}")
    return "\n".join(lines)


def clean_transcript_with_llm(client: OpenAIClient, model: str, segments: list[TranscriptSegment]) -> CleanTranscript:
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


def summarize_meeting_with_llm(client: OpenAIClient, model: str, cleaned: CleanTranscript) -> MeetingSummary:
    payload = client.generate_json(
        model=model,
        instructions=(
            "Analyze the cleaned meeting transcript. Return JSON with keys: paragraph, themes, "
            "action_items, resources, talk_points. The paragraph must be one paragraph. Include "
            "themes as plain-English topics with optional details, action items with mentioner, "
            "description, and quote when available, and resources with name, type, and context when "
            "available. For each talk point include speaker, salient_points, questions, and direct "
            "quotes wherever possible."
        ),
        input_text=transcript_to_text(cleaned.segments),
    )
    return MeetingSummary(
        paragraph=payload["paragraph"],
        themes=[_coerce_theme(item) for item in payload.get("themes", [])],
        action_items=[
            ActionItem(
                mentioner=_coerce_text(item.get("mentioner") if isinstance(item, dict) else None)
                or _coerce_text(item.get("owner") if isinstance(item, dict) else None)
                or "Unknown",
                description=_coerce_text(item.get("description") if isinstance(item, dict) else item) or "No action recorded.",
                quote=_coerce_string_field(item.get("quote") if isinstance(item, dict) else None),
            )
            for item in payload.get("action_items", [])
        ],
        resources=[_coerce_resource(item) for item in payload.get("resources", [])],
        talk_points=[
            TalkPoint(
                speaker=item["speaker"],
                salient_points=list(item.get("salient_points", [])),
                questions=list(item.get("questions", [])),
                quotes=list(item.get("quotes", [])),
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
    payload = client.generate_json(
        model=model,
        instructions=(
            "Cross-reference the provided focus area against the meeting summary and cleaned transcript. "
            "Return JSON with keys: relevant_points, outstanding_questions, action_items, quotes, "
            "coverage_note. Prefer direct quotes from the transcript when available."
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
    return FocusAreaReview(
        focus_area=focus_area,
        relevant_points=_coerce_text_list(payload.get("relevant_points", [])),
        outstanding_questions=_coerce_text_list(payload.get("outstanding_questions", [])),
        action_items=_coerce_text_list(payload.get("action_items", [])),
        quotes=_coerce_text_list(payload.get("quotes", [])),
        coverage_note=_coerce_text(payload.get("coverage_note")) or "No coverage note provided.",
    )
