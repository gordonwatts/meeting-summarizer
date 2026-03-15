from __future__ import annotations

import logging

from meeting_summarizer.config import DEFAULT_MAX_CLEAN_CHARS
from meeting_summarizer.models import (
    CleanTranscript,
    FocusAreaReview,
    MeetingSummary,
    ProjectConfig,
    TranscriptSegment,
)
from meeting_summarizer.openai_client import OpenAIClient
from meeting_summarizer.analysis.llm_stages import (
    clean_transcript_with_llm,
    cross_reference_with_llm,
    summarize_meeting_with_llm,
)

LOGGER = logging.getLogger(__name__)


def _segment_text_length(segment: TranscriptSegment) -> int:
    prefix = segment.speaker
    if segment.start_time:
        prefix = f"{prefix} [{segment.start_time}]"
    return len(f"{prefix}: {segment.text}\n")


def chunk_transcript_segments(
    segments: list[TranscriptSegment],
    max_chars: int = DEFAULT_MAX_CLEAN_CHARS,
) -> list[list[TranscriptSegment]]:
    if max_chars <= 0:
        raise ValueError("max_chars must be greater than zero.")
    if not segments:
        return []

    chunks: list[list[TranscriptSegment]] = []
    current_chunk: list[TranscriptSegment] = []
    current_length = 0

    for segment in segments:
        segment_length = _segment_text_length(segment)
        if current_chunk and current_length + segment_length > max_chars:
            chunks.append(current_chunk)
            current_chunk = []
            current_length = 0
        current_chunk.append(segment)
        current_length += segment_length

    if current_chunk:
        chunks.append(current_chunk)
    return chunks


def clean_transcript(
    segments: list[TranscriptSegment],
    client: OpenAIClient,
    model: str,
    max_chunk_chars: int = DEFAULT_MAX_CLEAN_CHARS,
) -> CleanTranscript:
    LOGGER.info("Cleaning transcript")
    chunks = chunk_transcript_segments(segments, max_chars=max_chunk_chars)
    LOGGER.debug(
        f"Cleaning transcript in {len(chunks)} chunk(s) with max_chunk_chars={max_chunk_chars}"
    )
    cleaned_segments: list[TranscriptSegment] = []
    for chunk in chunks:
        cleaned_segments.extend(
            clean_transcript_with_llm(client, model, chunk).segments
        )
    return CleanTranscript(segments=cleaned_segments)


def summarize_meeting(
    cleaned: CleanTranscript, client: OpenAIClient, model: str
) -> MeetingSummary:
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
