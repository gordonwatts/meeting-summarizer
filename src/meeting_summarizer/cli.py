from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from meeting_summarizer.analysis.pipeline import clean_transcript, cross_reference_focus_areas, summarize_meeting
from meeting_summarizer.config import (
    DEFAULT_MAX_CLEAN_CHARS,
    DEFAULT_MODEL_ECONOMY,
    DEFAULT_MODEL_JUDGMENT,
    resolve_api_key,
    store_api_key,
)
from meeting_summarizer.logging_config import configure_logging
from meeting_summarizer.models import CleanTranscript, MeetingSummary
from meeting_summarizer.openai_client import OpenAIClient
from meeting_summarizer.project import add_focus_area, init_project, load_project
from meeting_summarizer.render import (
    derive_output_path,
    parse_cleaned_markdown,
    parse_summary_markdown,
    render_cleaned_markdown,
    render_focus_area_markdown,
    render_summary_markdown,
    show_project,
)
from meeting_summarizer.transcripts.parser import parse_transcript

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
app.add_typer(project_app, name="project", help="Create, update, and inspect the project YAML file.")
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


def _write_markdown(output_path: Path, content: str, overwrite: bool) -> None:
    if output_path.exists() and not overwrite:
        raise typer.BadParameter(f"{output_path} already exists. Use --overwrite to replace it.")
    output_path.write_text(content, encoding="utf-8")


def _resolve_models(project_models: dict[str, str] | None, economy: str | None, judgment: str | None) -> tuple[str, str]:
    models = project_models or {}
    return (
        economy or models.get("economy", DEFAULT_MODEL_ECONOMY),
        judgment or models.get("judgment", DEFAULT_MODEL_JUDGMENT),
    )


def _load_or_clean_transcript(
    transcript_path: str,
    output_dir: str | None,
    client: OpenAIClient,
    economy_model: str,
    max_clean_chars: int,
    overwrite: bool,
) -> tuple[CleanTranscript, Path, bool]:
    cleaned_path = derive_output_path(transcript_path, ".cleaned.md", output_dir)
    if cleaned_path.exists():
        logger.info("Reusing existing cleaned transcript at %s", cleaned_path)
        cleaned = parse_cleaned_markdown(cleaned_path.read_text(encoding="utf-8"))
        return cleaned, cleaned_path, True

    cleaned = clean_transcript(parse_transcript(transcript_path), client, economy_model, max_clean_chars)
    _write_markdown(cleaned_path, render_cleaned_markdown(cleaned), overwrite)
    return cleaned, cleaned_path, False


def _load_or_summarize_meeting(
    transcript_path: str,
    output_dir: str | None,
    cleaned: CleanTranscript,
    client: OpenAIClient,
    judgment_model: str,
    overwrite: bool,
) -> tuple[MeetingSummary, Path, bool]:
    summary_path = derive_output_path(transcript_path, ".summary.md", output_dir)
    if summary_path.exists():
        logger.info("Reusing existing meeting summary at %s", summary_path)
        summary = parse_summary_markdown(summary_path.read_text(encoding="utf-8"))
        return summary, summary_path, True

    summary = summarize_meeting(cleaned, client, judgment_model)
    _write_markdown(summary_path, render_summary_markdown(summary), overwrite)
    return summary, summary_path, False


@project_app.command(
    "init",
    help="Create a new project YAML file with the given project name.",
    short_help="Create a project YAML file.",
)
def project_init(path: str, name: str = typer.Option(..., "--name")) -> None:
    project = init_project(path, name)
    typer.echo(f"Initialized project at {project.path}")


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
    area = add_focus_area(path, title, description, notes)
    typer.echo(f"Added focus area {area.id}")


@project_app.command(
    "show",
    help="Render the project YAML file as formatted terminal output.",
    short_help="Show the project configuration.",
)
def project_show(path: str) -> None:
    show_project(load_project(path), Console())


@auth_app.command(
    "api-key",
    help="Store the OpenAI API key in the user's home-directory .env file for this app.",
    short_help="Store the API key.",
)
def auth_api_key(api_key: str = typer.Option(..., "--api-key")) -> None:
    typer.echo(f"Stored API key in {store_api_key(api_key)}")


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
    max_clean_chars: int = typer.Option(DEFAULT_MAX_CLEAN_CHARS, "--max-clean-chars", min=1),
) -> None:
    client = _make_client(api_key)
    economy_model, _ = _resolve_models(None, model_economy, None)
    cleaned = clean_transcript(parse_transcript(transcript_path), client, economy_model, max_clean_chars)
    output_path = derive_output_path(transcript_path, ".cleaned.md", output_dir)
    _write_markdown(output_path, render_cleaned_markdown(cleaned), overwrite)
    typer.echo(str(output_path))


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
    max_clean_chars: int = typer.Option(DEFAULT_MAX_CLEAN_CHARS, "--max-clean-chars", min=1),
) -> None:
    client = _make_client(api_key)
    economy_model, judgment_model = _resolve_models(None, model_economy, model_judgment)
    cleaned, _, _ = _load_or_clean_transcript(
        transcript_path, output_dir, client, economy_model, max_clean_chars, overwrite
    )
    _, summary_path, _ = _load_or_summarize_meeting(
        transcript_path, output_dir, cleaned, client, judgment_model, overwrite
    )
    typer.echo(str(summary_path))


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
    max_clean_chars: int = typer.Option(DEFAULT_MAX_CLEAN_CHARS, "--max-clean-chars", min=1),
) -> None:
    project_config = load_project(project)
    client = _make_client(api_key)
    economy_model, judgment_model = _resolve_models(project_config.models, model_economy, model_judgment)
    cleaned, _, _ = _load_or_clean_transcript(
        transcript_path, output_dir, client, economy_model, max_clean_chars, overwrite
    )
    summary, _, _ = _load_or_summarize_meeting(
        transcript_path, output_dir, cleaned, client, judgment_model, overwrite
    )
    reviews = cross_reference_focus_areas(summary, cleaned, project_config, client, economy_model)
    focus_path = derive_output_path(transcript_path, ".focus-areas.md", output_dir)
    _write_markdown(focus_path, render_focus_area_markdown(reviews), overwrite)
    typer.echo(str(focus_path))


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
    max_clean_chars: int = typer.Option(DEFAULT_MAX_CLEAN_CHARS, "--max-clean-chars", min=1),
) -> None:
    project_config = load_project(project)
    client = _make_client(api_key)
    economy_model, judgment_model = _resolve_models(project_config.models, model_economy, model_judgment)
    cleaned, cleaned_path, reused_cleaned = _load_or_clean_transcript(
        transcript_path, output_dir, client, economy_model, max_clean_chars, overwrite
    )
    summary, summary_path, reused_summary = _load_or_summarize_meeting(
        transcript_path, output_dir, cleaned, client, judgment_model, overwrite
    )
    reviews = cross_reference_focus_areas(summary, cleaned, project_config, client, economy_model)
    outputs = {
        derive_output_path(transcript_path, ".focus-areas.md", output_dir): render_focus_area_markdown(reviews),
    }
    if not reused_cleaned:
        outputs[cleaned_path] = render_cleaned_markdown(cleaned)
    if not reused_summary:
        outputs[summary_path] = render_summary_markdown(summary)
    for output_path, content in outputs.items():
        _write_markdown(output_path, content, overwrite)
    emitted_paths = [cleaned_path, summary_path, *outputs]
    seen_paths: set[Path] = set()
    for output_path in emitted_paths:
        if output_path in seen_paths:
            continue
        seen_paths.add(output_path)
        typer.echo(str(output_path))
