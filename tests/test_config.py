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


def test_store_api_key_preserves_existing_env_entries(workspace_tmp_path) -> None:
    env_path = workspace_tmp_path / ".env"
    env_path.write_text(
        "EXISTING_TOKEN=keep-me\n"
        "# comment\n"
        f"{config.API_KEY_ENV_VAR}=old-secret\n",
        encoding="utf-8",
    )

    written_path = config.store_api_key("new-secret", env_path=env_path)

    assert written_path == env_path
    assert env_path.read_text(encoding="utf-8") == (
        "EXISTING_TOKEN=keep-me\n"
        f"{config.API_KEY_ENV_VAR}=new-secret\n"
    )
    assert config.resolve_api_key(env_path=env_path) == "new-secret"


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
