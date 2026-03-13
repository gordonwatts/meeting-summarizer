from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import dotenv_values

LOGGER = logging.getLogger(__name__)
API_KEY_ENV_VAR = "MEETING_SUMMARIZER_OPENAI_API_KEY"
DEFAULT_MODEL_ECONOMY = "gpt-5-mini"
DEFAULT_MODEL_JUDGMENT = "gpt-5"


def home_env_path() -> Path:
    return Path.home() / ".env"


def resolve_api_key(explicit_api_key: str | None = None) -> str:
    if explicit_api_key:
        return explicit_api_key
    if env_api_key := os.getenv(API_KEY_ENV_VAR):
        return env_api_key

    env_path = home_env_path()
    if env_path.exists():
        values = dotenv_values(env_path)
        if file_api_key := values.get(API_KEY_ENV_VAR):
            return file_api_key

    raise ValueError(
        "OpenAI API key not found. Provide --api-key, set the environment variable, "
        f"or store {API_KEY_ENV_VAR} in {env_path}."
    )


def store_api_key(api_key: str) -> Path:
    env_path = home_env_path()
    entries: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                entries[key] = value

    entries[API_KEY_ENV_VAR] = api_key
    lines = [f"{key}={value}" for key, value in sorted(entries.items())]
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    LOGGER.info("Stored API key in %s", env_path)
    return env_path
