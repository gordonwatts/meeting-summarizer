from __future__ import annotations

import json
import logging
from dataclasses import asdict
from typing import Any

from openai import OpenAI

from meeting_summarizer.models import (
    ActionItem,
    CleanTranscript,
    FocusArea,
    FocusAreaReview,
    MeetingSummary,
    TalkPoint,
    TranscriptSegment,
)

LOGGER = logging.getLogger(__name__)


class OpenAIClient:
    def __init__(self, api_key: str):
        self._client = OpenAI(api_key=api_key)

    def generate_json(self, *, model: str, instructions: str, input_text: str) -> dict[str, Any]:
        LOGGER.debug("Calling OpenAI model=%s", model)
        response = self._client.responses.create(
            model=model,
            instructions=instructions,
            input=input_text,
            text={"format": {"type": "json_object"}},
        )
        output_text = getattr(response, "output_text", None)
        if not output_text:
            raise ValueError("OpenAI response did not contain output_text.")
        return json.loads(output_text)


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
            "that is not substantive. Preserve meaning and keep full sentences. Do not summarize. "
            "Return JSON with a 'segments' array. Each segment must include speaker, text, start_time, "
            "end_time, and source_lineage."
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
            "action items with mentioner, description, and quote when available. For each talk point "
            "include speaker, salient_points, questions, and direct quotes wherever possible."
        ),
        input_text=transcript_to_text(cleaned.segments),
    )
    return MeetingSummary(
        paragraph=payload["paragraph"],
        themes=list(payload.get("themes", [])),
        action_items=[
            ActionItem(
                mentioner=item["mentioner"],
                description=item["description"],
                quote=item.get("quote"),
            )
            for item in payload.get("action_items", [])
        ],
        resources=list(payload.get("resources", [])),
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
        relevant_points=list(payload.get("relevant_points", [])),
        outstanding_questions=list(payload.get("outstanding_questions", [])),
        action_items=list(payload.get("action_items", [])),
        quotes=list(payload.get("quotes", [])),
        coverage_note=payload.get("coverage_note", "No coverage note provided."),
    )
