from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from openai import OpenAI

LOGGER = logging.getLogger(__name__)


def _default_cache_dir() -> Path:
    """Return the default on-disk cache directory for model responses."""
    return Path(__file__).resolve().parents[2] / ".cache" / "meeting-summarizer"


class OpenAIClient:
    def __init__(self, api_key: str, cache_dir: Path | None = None):
        self._client = OpenAI(api_key=api_key)
        self._cache_dir = cache_dir or _default_cache_dir()

    def _cache_path(self, *, model: str, instructions: str, input_text: str) -> Path:
        """Build the cache filename for a model request payload."""
        payload = json.dumps(
            {
                "model": model,
                "instructions": instructions,
                "input_text": input_text,
                "response_format": {"type": "json_object"},
            },
            ensure_ascii=True,
            sort_keys=True,
        ).encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()
        return self._cache_dir / f"{digest}.json"

    def _read_cached_response(self, cache_path: Path) -> dict[str, Any] | None:
        """Load and validate a cached JSON payload if one exists."""
        if not cache_path.exists():
            return None
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            LOGGER.warning(f"Ignoring unreadable cache entry at {cache_path}")
            return None
        if (
            not isinstance(cached, dict)
            or "payload" not in cached
            or not isinstance(cached["payload"], dict)
        ):
            LOGGER.warning(f"Ignoring invalid cache entry at {cache_path}")
            return None
        LOGGER.debug(
            f"OpenAI cache hit model={cached.get('model', 'unknown')} path={cache_path}"
        )
        return cached["payload"]

    def _write_cached_response(
        self, cache_path: Path, *, model: str, payload: dict[str, Any]
    ) -> None:
        """Write a cache entry atomically to avoid partial files."""
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        record = {"model": model, "payload": payload}
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=cache_path.parent,
            delete=False,
            suffix=".tmp",
        ) as handle:
            json.dump(record, handle, ensure_ascii=True, sort_keys=True)
            handle.write("\n")
            temp_path = Path(handle.name)
        os.replace(temp_path, cache_path)

    def generate_json(
        self, *, model: str, instructions: str, input_text: str
    ) -> dict[str, Any]:
        """Request a JSON response, reusing the disk cache when available.

        Args:
            model: Model name for the request.
            instructions: System-style instructions for the model.
            input_text: User content for the request.

        Returns:
            The parsed JSON payload from the model response.
        """
        if not input_text.strip():
            raise ValueError("OpenAI input_text cannot be empty.")
        cache_path = self._cache_path(
            model=model, instructions=instructions, input_text=input_text
        )
        cached_payload = self._read_cached_response(cache_path)
        if cached_payload is not None:
            return cached_payload
        LOGGER.debug(f"Calling OpenAI model={model}")
        response = self._client.responses.create(
            model=model,
            instructions=instructions,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": f"Respond with JSON only.\n\n{input_text}",
                        }
                    ],
                }
            ],
            text={"format": {"type": "json_object"}},
        )
        output_text = getattr(response, "output_text", None)
        if not output_text:
            raise ValueError("OpenAI response did not contain output_text.")
        payload = json.loads(output_text)
        self._write_cached_response(cache_path, model=model, payload=payload)
        return payload
