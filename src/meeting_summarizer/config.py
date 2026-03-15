from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import dotenv_values

LOGGER = logging.getLogger(__name__)
API_KEY_ENV_VAR = "MEETING_SUMMARIZER_OPENAI_API_KEY"
DEFAULT_MODEL_ECONOMY = "gpt-5-mini"
DEFAULT_MODEL_JUDGMENT = "gpt-5.4"
DEFAULT_MAX_CLEAN_CHARS = 15_000


def home_env_path() -> Path:
    return Path.home() / ".env"


def resolve_api_key(
    explicit_api_key: str | None = None, env_path: Path | None = None
) -> str:
    """Resolve the OpenAI API key from CLI input, environment, or an env file.

    Args:
        explicit_api_key: API key provided directly by the caller.
        env_path: Optional path to the env file to inspect before falling back to
            the default home-directory env file.

    Returns:
        The resolved API key string.
    """
    if explicit_api_key:
        return explicit_api_key
    if env_api_key := os.getenv(API_KEY_ENV_VAR):
        return env_api_key

    resolved_env_path = env_path or home_env_path()
    if resolved_env_path.exists():
        values = dotenv_values(resolved_env_path)
        if file_api_key := values.get(API_KEY_ENV_VAR):
            return file_api_key

    raise ValueError(
        "OpenAI API key not found. Provide --api-key, set the environment variable, "
        f"or store {API_KEY_ENV_VAR} in {resolved_env_path}."
    )


def store_api_key(api_key: str, env_path: Path | None = None) -> Path:
    """Store the API key in the configured env file path.

    Args:
        api_key: API key value to persist.
        env_path: Optional path to the env file to update.

    Returns:
        The path that was written.
    """
    resolved_env_path = env_path or home_env_path()
    entries: dict[str, str] = {}
    if resolved_env_path.exists():
        for line in resolved_env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                entries[key] = value

    entries[API_KEY_ENV_VAR] = api_key
    lines = [f"{key}={value}" for key, value in sorted(entries.items())]
    resolved_env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    LOGGER.info(f"Stored API key in {resolved_env_path}")
    return resolved_env_path
