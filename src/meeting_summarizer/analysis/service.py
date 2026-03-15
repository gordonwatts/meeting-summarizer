from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from meeting_summarizer.analysis.pipeline import (
    clean_transcript,
    cross_reference_focus_areas,
    summarize_meeting,
)
from meeting_summarizer.markdown.cleaned import (
    parse_cleaned_markdown,
    render_cleaned_markdown,
)
from meeting_summarizer.markdown.focus_areas import render_focus_area_markdown
from meeting_summarizer.markdown.paths import derive_output_path
from meeting_summarizer.markdown.summary import (
    parse_summary_markdown,
    render_summary_markdown,
)
from meeting_summarizer.models import CleanTranscript, FocusAreaReview, MeetingSummary
from meeting_summarizer.openai_client import OpenAIClient
from meeting_summarizer.project import load_project
from meeting_summarizer.transcripts.parser import parse_transcript

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class TranscriptOutputSet:
    cleaned_path: Path
    summary_path: Path
    focus_path: Path

    def as_list(self) -> list[Path]:
        return [self.cleaned_path, self.summary_path, self.focus_path]


@dataclass(slots=True)
class TranscriptRunArtifacts:
    cleaned: CleanTranscript
    summary: MeetingSummary | None = None
    reviews: list[FocusAreaReview] | None = None


class TranscriptAnalysisService:
    def __init__(self, client: OpenAIClient):
        self._client = client

    def output_paths(
        self, transcript_path: str | Path, output_dir: str | Path | None = None
    ) -> TranscriptOutputSet:
        return TranscriptOutputSet(
            cleaned_path=derive_output_path(transcript_path, ".cleaned.md", output_dir),
            summary_path=derive_output_path(transcript_path, ".summary.md", output_dir),
            focus_path=derive_output_path(transcript_path, ".focus-areas.md", output_dir),
        )

    def clean_transcript(
        self,
        transcript_path: str | Path,
        *,
        output_dir: str | Path | None,
        model: str,
        max_clean_chars: int,
        overwrite: bool,
    ) -> tuple[CleanTranscript, Path, bool]:
        paths = self.output_paths(transcript_path, output_dir)
        if paths.cleaned_path.exists() and not overwrite:
            LOGGER.info(f"Reusing existing cleaned transcript at {paths.cleaned_path}")
            cleaned = parse_cleaned_markdown(
                paths.cleaned_path.read_text(encoding="utf-8")
            )
            return cleaned, paths.cleaned_path, True

        cleaned = clean_transcript(
            parse_transcript(transcript_path),
            self._client,
            model,
            max_clean_chars,
        )
        self._write_markdown(
            paths.cleaned_path, render_cleaned_markdown(cleaned), overwrite
        )
        return cleaned, paths.cleaned_path, False

    def summarize_meeting(
        self,
        transcript_path: str | Path,
        *,
        output_dir: str | Path | None,
        cleaned: CleanTranscript,
        model: str,
        overwrite: bool,
    ) -> tuple[MeetingSummary, Path, bool]:
        paths = self.output_paths(transcript_path, output_dir)
        if paths.summary_path.exists() and not overwrite:
            LOGGER.info(f"Reusing existing meeting summary at {paths.summary_path}")
            summary = parse_summary_markdown(
                paths.summary_path.read_text(encoding="utf-8")
            )
            return summary, paths.summary_path, True

        summary = summarize_meeting(cleaned, self._client, model)
        self._write_markdown(
            paths.summary_path, render_summary_markdown(summary), overwrite
        )
        return summary, paths.summary_path, False

    def cross_reference_focus_areas(
        self,
        transcript_path: str | Path,
        *,
        project_path: str | Path,
        output_dir: str | Path | None,
        summary: MeetingSummary,
        cleaned: CleanTranscript,
        model: str,
        overwrite: bool,
    ) -> tuple[list[FocusAreaReview], Path]:
        project_config = load_project(project_path)
        paths = self.output_paths(transcript_path, output_dir)
        reviews = cross_reference_focus_areas(
            summary, cleaned, project_config, self._client, model
        )
        self._write_markdown(
            paths.focus_path, render_focus_area_markdown(reviews), overwrite
        )
        return reviews, paths.focus_path

    def run_full_analysis(
        self,
        transcript_path: str | Path,
        *,
        project_path: str | Path,
        output_dir: str | Path | None,
        economy_model: str,
        judgment_model: str,
        max_clean_chars: int,
        overwrite: bool,
    ) -> TranscriptRunArtifacts:
        project_config = load_project(project_path)
        paths = self.output_paths(transcript_path, output_dir)
        if not overwrite and self.all_outputs_exist(paths.as_list()):
            LOGGER.info("All analysis outputs already exist; returning without work.")
            self.log_output_paths("Existing analysis output:", paths.as_list())
            return TranscriptRunArtifacts(
                cleaned=parse_cleaned_markdown(
                    paths.cleaned_path.read_text(encoding="utf-8")
                ),
                summary=parse_summary_markdown(
                    paths.summary_path.read_text(encoding="utf-8")
                ),
            )

        cleaned, _, _ = self.clean_transcript(
            transcript_path,
            output_dir=output_dir,
            model=economy_model,
            max_clean_chars=max_clean_chars,
            overwrite=overwrite,
        )
        summary, _, _ = self.summarize_meeting(
            transcript_path,
            output_dir=output_dir,
            cleaned=cleaned,
            model=judgment_model,
            overwrite=overwrite,
        )
        reviews: list[FocusAreaReview] | None = None
        if overwrite or not paths.focus_path.exists():
            reviews = cross_reference_focus_areas(
                summary, cleaned, project_config, self._client, economy_model
            )
            self._write_markdown(
                paths.focus_path, render_focus_area_markdown(reviews), overwrite
            )
        self.log_output_paths("Analysis output ready:", paths.as_list())
        return TranscriptRunArtifacts(cleaned=cleaned, summary=summary, reviews=reviews)

    @staticmethod
    def ensure_output_writable(output_path: Path, overwrite: bool) -> None:
        if output_path.exists() and not overwrite:
            raise ValueError(f"{output_path} already exists. Use --overwrite to replace it.")

    @staticmethod
    def all_outputs_exist(output_paths: list[Path]) -> bool:
        return all(output_path.exists() for output_path in output_paths)

    @staticmethod
    def log_output_paths(message: str, output_paths: list[Path]) -> None:
        for output_path in output_paths:
            LOGGER.info(f"{message} {output_path}")

    @staticmethod
    def _write_markdown(output_path: Path, content: str, overwrite: bool) -> None:
        TranscriptAnalysisService.ensure_output_writable(output_path, overwrite)
        output_path.write_text(content, encoding="utf-8")
