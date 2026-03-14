from __future__ import annotations

from types import SimpleNamespace

import pytest

from meeting_summarizer.openai_client import OpenAIClient


class FakeResponses:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_text='{"value": "cached"}')


class FakeSDKClient:
    def __init__(self, responses: FakeResponses) -> None:
        self.responses = responses


@pytest.fixture()
def fake_openai(monkeypatch: pytest.MonkeyPatch) -> FakeResponses:
    responses = FakeResponses()
    monkeypatch.setattr("meeting_summarizer.openai_client.OpenAI", lambda api_key: FakeSDKClient(responses))
    return responses


def test_generate_json_uses_disk_cache(workspace_tmp_path, fake_openai: FakeResponses) -> None:
    cache_dir = workspace_tmp_path / "cache"
    client = OpenAIClient(api_key="secret", cache_dir=cache_dir)

    first = client.generate_json(model="gpt-5-mini", instructions="Test instructions", input_text="hello")
    second = client.generate_json(model="gpt-5-mini", instructions="Test instructions", input_text="hello")

    assert first == {"value": "cached"}
    assert second == {"value": "cached"}
    assert len(fake_openai.calls) == 1
    assert len(list(cache_dir.glob("*.json"))) == 1


def test_generate_json_separates_distinct_cache_keys(workspace_tmp_path, fake_openai: FakeResponses) -> None:
    cache_dir = workspace_tmp_path / "cache"
    client = OpenAIClient(api_key="secret", cache_dir=cache_dir)

    client.generate_json(model="gpt-5-mini", instructions="First", input_text="hello")
    client.generate_json(model="gpt-5.4", instructions="First", input_text="hello")
    client.generate_json(model="gpt-5-mini", instructions="Second", input_text="hello")

    assert len(fake_openai.calls) == 3
    assert len(list(cache_dir.glob("*.json"))) == 3


def test_generate_json_ignores_invalid_cache_entries(workspace_tmp_path, fake_openai: FakeResponses) -> None:
    cache_dir = workspace_tmp_path / "cache"
    client = OpenAIClient(api_key="secret", cache_dir=cache_dir)
    cache_path = client._cache_path(model="gpt-5-mini", instructions="Test instructions", input_text="hello")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text("not-json", encoding="utf-8")

    payload = client.generate_json(model="gpt-5-mini", instructions="Test instructions", input_text="hello")

    assert payload == {"value": "cached"}
    assert len(fake_openai.calls) == 1
