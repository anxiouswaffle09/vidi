import os
from pathlib import Path
from unittest.mock import patch

import pytest

from vidi.config import get_api_key, get_config_path, load_config, save_config, mask_key


def test_get_config_path_returns_path():
    path = get_config_path()
    assert path.name == "config.toml"
    assert "vidi" in str(path)


def test_get_api_key_from_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "env-key-123")
    key = get_api_key(prompt_if_missing=False)
    assert key == "env-key-123"


def test_get_api_key_from_config(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    config_file = tmp_path / "config.toml"
    config_file.write_text('[api]\ngemini_key = "file-key-456"\n')
    with patch("vidi.config.get_config_path", return_value=config_file):
        key = get_api_key(prompt_if_missing=False)
    assert key == "file-key-456"


def test_get_api_key_returns_none_when_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    config_file = tmp_path / "nonexistent.toml"
    with patch("vidi.config.get_config_path", return_value=config_file):
        key = get_api_key(prompt_if_missing=False)
    assert key is None


def test_env_var_takes_precedence_over_config(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "env-key")
    config_file = tmp_path / "config.toml"
    config_file.write_text('[api]\ngemini_key = "file-key"\n')
    with patch("vidi.config.get_config_path", return_value=config_file):
        key = get_api_key(prompt_if_missing=False)
    assert key == "env-key"


def test_save_config_creates_file(tmp_path):
    config_file = tmp_path / "vidi" / "config.toml"
    with patch("vidi.config.get_config_path", return_value=config_file):
        save_config("gemini_key", "new-key-789")
    assert config_file.exists()
    content = config_file.read_text()
    assert "new-key-789" in content


def test_save_config_updates_existing(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('[api]\ngemini_key = "old-key"\n')
    with patch("vidi.config.get_config_path", return_value=config_file):
        save_config("gemini_key", "updated-key")
    content = config_file.read_text()
    assert "updated-key" in content
    assert "old-key" not in content


def test_load_config_returns_empty_for_missing_file(tmp_path):
    config_file = tmp_path / "nonexistent.toml"
    with patch("vidi.config.get_config_path", return_value=config_file):
        config = load_config()
    assert config == {}


def test_mask_key():
    assert mask_key("abcdefghij") == "abcd...ghij"
    assert mask_key("abc") == "***"
    assert mask_key(None) == "(not set)"


def test_save_config_escapes_special_chars_in_value(tmp_path):
    config_file = tmp_path / "config.toml"
    with patch("vidi.config.get_config_path", return_value=config_file):
        save_config("gemini_key", 'key"with"quotes')
    content = config_file.read_text()
    assert '"' not in content.split("=")[1].strip().strip('"') or '\\"' in content


def test_save_config_rejects_invalid_key(tmp_path):
    config_file = tmp_path / "config.toml"
    with patch("vidi.config.get_config_path", return_value=config_file):
        with pytest.raises(ValueError, match="Unknown config key"):
            save_config("malicious_key", "value")


def test_save_config_roundtrips_with_special_value(tmp_path):
    config_file = tmp_path / "config.toml"
    with patch("vidi.config.get_config_path", return_value=config_file):
        save_config("gemini_key", 'has"quotes\\and\\backslashes')
    with patch("vidi.config.get_config_path", return_value=config_file):
        config = load_config()
    assert config["api"]["gemini_key"] == 'has"quotes\\and\\backslashes'
