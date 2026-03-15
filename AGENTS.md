# AGENTS.md

## Purpose
- Build and maintain a Python CLI that parses Zoom transcripts, cleans them without summarizing, summarizes the cleaned transcript, and cross-references focus areas from a project YAML file.

## Package Layout
- Put CLI wiring in `src/meeting_summarizer/cli.py`.
- Put project YAML logic in `src/meeting_summarizer/project.py`.
- Put OpenAI configuration and client creation in `src/meeting_summarizer/config.py` and `src/meeting_summarizer/openai_client.py`.
- Put transcript parsing in `src/meeting_summarizer/transcripts/`.
- Put prompt-building and stage logic in `src/meeting_summarizer/analysis/`.
- Put Markdown rendering and output path helpers in `src/meeting_summarizer/render.py`.

## Rules
- Route all OpenAI access through the shared client wrapper. Do not instantiate SDK clients directly in CLI commands or analysis modules.
- Use Python `logging` for warnings, info, and debug output. Respect the global `-v` and `-vv` flags.
- When a project path has no extension, resolve it to `.yaml`.
- Prompts should prefer direct quotes and preserve traceability back to cleaned transcript content.
- Keep analysis stages factored so tests can mock LLM responses without patching unrelated logic.
- Docstrings:
  - Private functions that start with `_` should usually have a short one- or two-line docstring unless they are truly trivial.
  - Obvious one- or two-line functions do not need a docstring.
  - Public functions used across modules should have a full docstring that documents arguments and returns.

## Tests
- Add or update tests for transcript parsing, project YAML behavior, Markdown rendering, CLI behavior, and every OpenAI-backed stage with mocked responses.
- Avoid live network calls in tests.
