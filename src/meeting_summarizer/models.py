from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class TranscriptSegment:
    speaker: str
    text: str
    start_time: str | None = None
    end_time: str | None = None
    source_lineage: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CleanTranscript:
    segments: list[TranscriptSegment]


@dataclass(slots=True)
class ActionItem:
    mentioner: str
    description: str
    quote: str | None = None


@dataclass(slots=True)
class SummaryTheme:
    title: str
    details: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ExternalResource:
    name: str
    resource_type: str | None = None
    context: str | None = None


@dataclass(slots=True)
class TalkPoint:
    speaker: str
    salient_points: list[str]
    questions: list[str]
    quotes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MeetingSummary:
    paragraph: str
    themes: list[SummaryTheme]
    action_items: list[ActionItem]
    resources: list[ExternalResource]
    talk_points: list[TalkPoint]


@dataclass(slots=True)
class FocusArea:
    id: str
    title: str
    description: str
    notes: str | None = None


@dataclass(slots=True)
class FocusAreaReview:
    focus_area: FocusArea
    mentioned_people: list[str]
    relevant_points: list[str]
    outstanding_questions: list[str]
    action_items: list[str]
    quotes: list[str]
    coverage_note: str


@dataclass(slots=True)
class ProjectConfig:
    name: str
    focus_areas: list[FocusArea]
    models: dict[str, str] = field(default_factory=dict)
    path: Path | None = None
