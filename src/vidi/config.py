from __future__ import annotations

import os
import sys
import tomllib
from pathlib import Path


def get_config_path() -> Path:
    return Path.home() / ".config" / "vidi" / "config.toml"


def load_config() -> dict:
    path = get_config_path()
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f)


def _toml_escape(value: str) -> str:
    """Escape a string for use inside a TOML double-quoted basic string."""
    value = value.replace("\\", "\\\\")
    value = value.replace('"', '\\"')
    value = value.replace("\n", "\\n")
    value = value.replace("\r", "\\r")
    value = value.replace("\t", "\\t")
    return value


_VALID_CONFIG_KEYS = {"gemini_key", "youtube_key"}


def save_config(key: str, value: str) -> None:
    if key not in _VALID_CONFIG_KEYS:
        raise ValueError(f"Unknown config key: {key}. Valid keys: {', '.join(sorted(_VALID_CONFIG_KEYS))}")
    path = get_config_path()
    config = load_config()

    api = config.get("api", {})
    api[key] = value
    config["api"] = api

    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["[api]\n"]
    for k, v in config["api"].items():
        lines.append(f'{k} = "{_toml_escape(v)}"\n')
    path.write_text("".join(lines))


def get_api_key(prompt_if_missing: bool = True) -> str | None:
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key

    config = load_config()
    key = config.get("api", {}).get("gemini_key")
    if key:
        return key

    if prompt_if_missing and sys.stdin.isatty():
        return _prompt_for_key()

    return None


def _prompt_for_key() -> str | None:
    print("\nNo Gemini API key found.\n")
    print("1. Go to https://aistudio.google.com/apikey")
    print("2. Create an API key")
    print("3. Paste it below\n")
    try:
        key = input("Gemini API key: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    if not key:
        return None
    save_config("gemini_key", key)
    path = get_config_path()
    print(f"\n✓ Key saved to {path}")
    return key


def mask_key(key: str | None) -> str:
    if key is None:
        return "(not set)"
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"
