from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from meeting_summarizer.analysis.service import TranscriptAnalysisService
from meeting_summarizer.config import (
    DEFAULT_MAX_CLEAN_CHARS,
    DEFAULT_MODEL_ECONOMY,
    DEFAULT_MODEL_JUDGMENT,
    resolve_api_key,
    store_api_key,
)
from meeting_summarizer.logging_config import configure_logging
from meeting_summarizer.markdown.paths import derive_output_path
from meeting_summarizer.markdown.project_display import show_project
from meeting_summarizer.openai_client import OpenAIClient
from meeting_summarizer.project import add_focus_area, init_project, load_project

app = typer.Typer(
    no_args_is_help=True,
    help="Clean Zoom transcripts, summarize meetings, and cross-reference project focus areas.",
)
project_app = typer.Typer(
    no_args_is_help=True,
    help="Create, update, and inspect the project YAML file.",
)
auth_app = typer.Typer(
    no_args_is_help=True,
    help="Manage OpenAI API credentials for this app.",
)
transcript_app = typer.Typer(
    no_args_is_help=True,
    help="Run transcript cleaning, summarization, and focus-area analysis.",
)
app.add_typer(
    project_app,
    name="project",
    help="Create, update, and inspect the project YAML file.",
)
app.add_typer(auth_app, name="auth", help="Manage OpenAI API credentials for this app.")
app.add_typer(
    transcript_app,
    name="transcript",
    help="Run transcript cleaning, summarization, and focus-area analysis.",
)

logger = logging.getLogger(__name__)


@app.callback()
def main(verbose: Annotated[int, typer.Option("-v", count=True)] = 0) -> None:
    configure_logging(verbose)


def _make_client(api_key: str | None) -> OpenAIClient:
    return OpenAIClient(api_key=resolve_api_key(api_key))


def _make_service(api_key: str | None) -> TranscriptAnalysisService:
    return TranscriptAnalysisService(_make_client(api_key))


def _resolve_models(
    project_models: dict[str, str] | None, economy: str | None, judgment: str | None
) -> tuple[str, str]:
    models = project_models or {}
    return (
        economy or models.get("economy", DEFAULT_MODEL_ECONOMY),
        judgment or models.get("judgment", DEFAULT_MODEL_JUDGMENT),
    )


@project_app.command(
    "init",
    help="Create a new project YAML file with the given project name.",
    short_help="Create a project YAML file.",
)
def project_init(path: str, name: str = typer.Option(..., "--name")) -> None:
    project = init_project(path, name)
    logger.info(f"Initialized project at {project.path}")


@project_app.command(
    "add-focus-area",
    help="Append one focus area to the project YAML file.",
    short_help="Add a focus area.",
)
def project_add_focus_area(
    path: str,
    title: str = typer.Option(..., "--title"),
    description: str = typer.Option(..., "--description"),
    notes: str | None = typer.Option(None, "--notes"),
) -> None:
    try:
        area = add_focus_area(path, title, description, notes)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    logger.info(f"Added focus area {area.id}")


@project_app.command(
    "show",
    help="Render the project YAML file as formatted terminal output.",
    short_help="Show the project configuration.",
)
def project_show(path: str) -> None:
    try:
        project = load_project(path)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    show_project(project, Console())


@auth_app.command(
    "api-key",
    help="Store the OpenAI API key in the user's home-directory .env file for this app.",
    short_help="Store the API key.",
)
def auth_api_key(api_key: str = typer.Option(..., "--api-key")) -> None:
    logger.info(f"Stored API key in {store_api_key(api_key)}")


@transcript_app.command(
    "clean",
    help="Clean a transcript and write a Markdown transcript with filler and operational chatter removed.",
    short_help="Clean a transcript.",
)
def transcript_clean(
    transcript_path: str,
    api_key: str | None = typer.Option(None, "--api-key"),
    output_dir: str | None = typer.Option(None, "--output-dir"),
    overwrite: bool = typer.Option(False, "--overwrite"),
    model_economy: str | None = typer.Option(
        None,
        "--model-economy",
        help="Model used for the transcript cleaning phase.",
        show_default=DEFAULT_MODEL_ECONOMY,
    ),
    max_clean_chars: int = typer.Option(
        DEFAULT_MAX_CLEAN_CHARS, "--max-clean-chars", min=1
    ),
) -> None:
    output_path = derive_output_path(transcript_path, ".cleaned.md", output_dir)
    service = _make_service(api_key)
    _guard_writable_output(output_path, overwrite)
    economy_model, _ = _resolve_models(None, model_economy, None)
    _, output_path, _ = service.clean_transcript(
        transcript_path,
        output_dir=output_dir,
        model=economy_model,
        max_clean_chars=max_clean_chars,
        overwrite=overwrite,
    )
    logger.info(f"Wrote cleaned transcript to {output_path}")


@transcript_app.command(
    "summarize",
    help="Clean a transcript, summarize the cleaned content, and write Markdown outputs.",
    short_help="Summarize a transcript.",
)
def transcript_summarize(
    transcript_path: str,
    api_key: str | None = typer.Option(None, "--api-key"),
    output_dir: str | None = typer.Option(None, "--output-dir"),
    overwrite: bool = typer.Option(False, "--overwrite"),
    model_economy: str | None = typer.Option(
        None,
        "--model-economy",
        help="Model used for the transcript cleaning phase.",
        show_default=DEFAULT_MODEL_ECONOMY,
    ),
    model_judgment: str | None = typer.Option(
        None,
        "--model-judgment",
        help="Model used for the meeting summarization phase.",
        show_default=DEFAULT_MODEL_JUDGMENT,
    ),
    max_clean_chars: int = typer.Option(
        DEFAULT_MAX_CLEAN_CHARS, "--max-clean-chars", min=1
    ),
) -> None:
    summary_path = derive_output_path(transcript_path, ".summary.md", output_dir)
    service = _make_service(api_key)
    _guard_writable_output(summary_path, overwrite)
    economy_model, judgment_model = _resolve_models(None, model_economy, model_judgment)
    cleaned, _, _ = service.clean_transcript(
        transcript_path,
        output_dir=output_dir,
        model=economy_model,
        max_clean_chars=max_clean_chars,
        overwrite=overwrite,
    )
    _, summary_path, _ = service.summarize_meeting(
        transcript_path,
        output_dir=output_dir,
        cleaned=cleaned,
        model=judgment_model,
        overwrite=overwrite,
    )
    logger.info(f"Wrote meeting summary to {summary_path}")


@transcript_app.command(
    "cross-reference",
    help="Clean and summarize a transcript, then cross-reference the results against project focus areas.",
    short_help="Cross-reference focus areas.",
)
def transcript_cross_reference(
    transcript_path: str,
    project: str = typer.Option(..., "--project"),
    api_key: str | None = typer.Option(None, "--api-key"),
    output_dir: str | None = typer.Option(None, "--output-dir"),
    overwrite: bool = typer.Option(False, "--overwrite"),
    model_economy: str | None = typer.Option(
        None,
        "--model-economy",
        help="Model used for transcript cleaning and focus-area cross-reference phases.",
        show_default=DEFAULT_MODEL_ECONOMY,
    ),
    model_judgment: str | None = typer.Option(
        None,
        "--model-judgment",
        help="Model used for the meeting summarization phase.",
        show_default=DEFAULT_MODEL_JUDGMENT,
    ),
    max_clean_chars: int = typer.Option(
        DEFAULT_MAX_CLEAN_CHARS, "--max-clean-chars", min=1
    ),
) -> None:
    try:
        project_config = load_project(project)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    focus_path = derive_output_path(transcript_path, ".focus-areas.md", output_dir)
    service = _make_service(api_key)
    _guard_writable_output(focus_path, overwrite)
    economy_model, judgment_model = _resolve_models(
        project_config.models, model_economy, model_judgment
    )
    cleaned, _, _ = service.clean_transcript(
        transcript_path,
        output_dir=output_dir,
        model=economy_model,
        max_clean_chars=max_clean_chars,
        overwrite=overwrite,
    )
    summary, _, _ = service.summarize_meeting(
        transcript_path,
        output_dir=output_dir,
        cleaned=cleaned,
        model=judgment_model,
        overwrite=overwrite,
    )
    _, focus_path = service.cross_reference_focus_areas(
        transcript_path,
        project_path=project,
        output_dir=output_dir,
        summary=summary,
        cleaned=cleaned,
        model=economy_model,
        overwrite=overwrite,
    )
    logger.info(f"Wrote focus-area cross reference to {focus_path}")


@transcript_app.command(
    "analysis",
    help="Run the full transcript pipeline: clean, summarize, and cross-reference focus areas.",
    short_help="Run the full analysis pipeline.",
)
def transcript_analysis(
    transcript_path: str,
    project: str = typer.Option(..., "--project"),
    api_key: str | None = typer.Option(None, "--api-key"),
    output_dir: str | None = typer.Option(None, "--output-dir"),
    overwrite: bool = typer.Option(False, "--overwrite"),
    model_economy: str | None = typer.Option(
        None,
        "--model-economy",
        help="Model used for transcript cleaning and focus-area cross-reference phases.",
        show_default=DEFAULT_MODEL_ECONOMY,
    ),
    model_judgment: str | None = typer.Option(
        None,
        "--model-judgment",
        help="Model used for the meeting summarization phase.",
        show_default=DEFAULT_MODEL_JUDGMENT,
    ),
    max_clean_chars: int = typer.Option(
        DEFAULT_MAX_CLEAN_CHARS, "--max-clean-chars", min=1
    ),
) -> None:
    try:
        project_config = load_project(project)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    output_paths = [
        derive_output_path(transcript_path, ".cleaned.md", output_dir),
        derive_output_path(transcript_path, ".summary.md", output_dir),
        derive_output_path(transcript_path, ".focus-areas.md", output_dir),
    ]
    if not overwrite and TranscriptAnalysisService.all_outputs_exist(output_paths):
        TranscriptAnalysisService.log_output_paths(
            "Existing analysis output:", output_paths
        )
        return
    service = _make_service(api_key)
    economy_model, judgment_model = _resolve_models(
        project_config.models, model_economy, model_judgment
    )
    service.run_full_analysis(
        transcript_path,
        project_path=project,
        output_dir=output_dir,
        economy_model=economy_model,
        judgment_model=judgment_model,
        max_clean_chars=max_clean_chars,
        overwrite=overwrite,
    )


def _guard_writable_output(output_path: Path, overwrite: bool) -> None:
    try:
        TranscriptAnalysisService.ensure_output_writable(output_path, overwrite)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
