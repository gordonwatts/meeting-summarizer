from __future__ import annotations

import logging

from meeting_summarizer.models import CleanTranscript, FocusAreaReview, MeetingSummary, ProjectConfig
from meeting_summarizer.openai_client import (
    OpenAIClient,
    clean_transcript_with_llm,
    cross_reference_with_llm,
    summarize_meeting_with_llm,
)

LOGGER = logging.getLogger(__name__)


def clean_transcript(segments, client: OpenAIClient, model: str) -> CleanTranscript:
    LOGGER.info("Cleaning transcript")
    return clean_transcript_with_llm(client, model, segments)


def summarize_meeting(cleaned: CleanTranscript, client: OpenAIClient, model: str) -> MeetingSummary:
    LOGGER.info("Summarizing meeting")
    return summarize_meeting_with_llm(client, model, cleaned)


def cross_reference_focus_areas(
    summary: MeetingSummary,
    cleaned: CleanTranscript,
    project: ProjectConfig,
    client: OpenAIClient,
    model: str,
) -> list[FocusAreaReview]:
    LOGGER.info("Cross-referencing focus areas")
    return [
        cross_reference_with_llm(client, model, summary, cleaned, focus_area)
        for focus_area in project.focus_areas
    ]
