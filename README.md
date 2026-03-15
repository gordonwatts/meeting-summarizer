# meeting-summarizer

CLI tools for cleaning Zoom transcripts, generating meeting summaries, and cross-referencing project focus areas.

## Development

Run tests in this sandbox with:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

If `.venv` is missing or stale, rebuild it in a shell where `uv` works:

```powershell
uv sync --extra dev
```

Then continue using the explicit `.venv` Python path above for local test runs.

## Models

- The economy model is used for transcript cleaning and focus-area cross-reference.
- The judgment model is used for meeting summarization.
- Project YAML `models.economy` and `models.judgment` override those defaults for transcript commands that load a project.
