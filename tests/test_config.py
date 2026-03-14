from __future__ import annotations

import pytest

from meeting_summarizer import config


def test_store_and_resolve_api_key(
    workspace_tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = workspace_tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(config.Path, "home", lambda: home)
    env_path = config.store_api_key("secret")
    assert env_path == home / ".env"
    assert config.resolve_api_key() == "secret"


def test_cli_api_key_precedence(
    monkeypatch: pytest.MonkeyPatch, workspace_tmp_path
) -> None:
    home = workspace_tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(config.Path, "home", lambda: home)
    (home / ".env").write_text(
        f"{config.API_KEY_ENV_VAR}=from-file\n", encoding="utf-8"
    )
    monkeypatch.setenv(config.API_KEY_ENV_VAR, "from-env")
    assert config.resolve_api_key("from-cli") == "from-cli"
    assert config.resolve_api_key() == "from-env"
