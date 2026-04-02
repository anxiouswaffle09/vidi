# vidi Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI tool that sends YouTube URLs to Google's Gemini API for video analysis and writes structured output to disk.

**Architecture:** Five modules — `config.py` (API key management), `output.py` (folder/file I/O, path sanitization), `video.py` (yt-dlp/ffmpeg subprocess wrappers), `gemini.py` (Gemini API client, prompts, session management), `cli.py` (typer commands). Each layer has one job. `cli.py` orchestrates. Tests and semgrep scans alongside every task.

**Tech Stack:** Python 3.11+, typer, google-generativeai, uv, pytest, semgrep

---

## File Structure

```
pyproject.toml                  ← project metadata, dependencies, [project.scripts] entry point
src/vidi/__init__.py            ← package root, __version__
src/vidi/config.py              ← API key lookup (env → toml → prompt), config commands
src/vidi/output.py              ← path sanitization, folder creation, file writing, skip/force, session I/O
src/vidi/video.py               ← yt-dlp/ffmpeg subprocess wrappers, dependency detection
src/vidi/gemini.py              ← Gemini client, prompts, response parsing, chat sessions
src/vidi/cli.py                 ← typer app, all command definitions
tests/test_config.py            ← config module tests
tests/test_output.py            ← output module tests
tests/test_video.py             ← video module tests
tests/test_gemini.py            ← gemini module tests
tests/test_cli.py               ← CLI integration tests
progress.txt                    ← updated after each task
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/vidi/__init__.py`
- Create: `src/vidi/cli.py`
- Create: `progress.txt`

- [ ] **Step 1: Initialize git repo**

```bash
cd /home/wendy/Projects/vidi
git init
```

- [ ] **Step 2: Create `.gitignore`**

Create `.gitignore`:

```
__pycache__/
*.pyc
.venv/
dist/
*.egg-info/
.env
vidi/
```

- [ ] **Step 3: Create `pyproject.toml`**

```toml
[project]
name = "vidi"
version = "0.1.0"
description = "YouTube video analyzer powered by Google Gemini"
requires-python = ">=3.11"
dependencies = [
    "typer>=0.9.0",
    "google-generativeai>=0.8.0",
]

[project.scripts]
vidi = "vidi.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/vidi"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
]
```

- [ ] **Step 4: Create `src/vidi/__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 5: Create minimal `src/vidi/cli.py`**

```python
import typer

app = typer.Typer(
    name="vidi",
    help="YouTube video analyzer powered by Google Gemini.",
    add_completion=False,
)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
```

- [ ] **Step 6: Create `progress.txt`**

```
# vidi Implementation Progress

## Task 1: Project Scaffolding
- [x] Completed
```

- [ ] **Step 7: Install and verify**

```bash
cd /home/wendy/Projects/vidi
uv venv
uv pip install -e ".[dev]"
vidi --help
```

Expected: help text with "YouTube video analyzer powered by Google Gemini."

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml src/ tests/ .gitignore progress.txt
git commit -m "feat: scaffold vidi project with typer CLI"
```

---

### Task 2: Config Module

**Files:**
- Create: `src/vidi/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests for config**

Create `tests/test_config.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/wendy/Projects/vidi
uv run pytest tests/test_config.py -v
```

Expected: ImportError — `vidi.config` does not exist.

- [ ] **Step 3: Implement `src/vidi/config.py`**

```python
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


def save_config(key: str, value: str) -> None:
    path = get_config_path()
    config = load_config()

    api = config.get("api", {})
    api[key] = value
    config["api"] = api

    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["[api]\n"]
    for k, v in config["api"].items():
        lines.append(f'{k} = "{v}"\n')
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_config.py -v
```

Expected: all 10 tests PASS.

- [ ] **Step 5: Run semgrep on config module**

```bash
semgrep --config auto src/vidi/config.py --json 2>/dev/null | python3 -m json.tool
```

Review findings. The `input()` call for the API key prompt is intentional (interactive first-run setup, gated behind `sys.stdin.isatty()`). Fix any real issues.

- [ ] **Step 6: Update progress.txt and commit**

```bash
git add src/vidi/config.py tests/test_config.py progress.txt
git commit -m "feat: add config module with API key management"
```

---

### Task 3: Output Module

**Files:**
- Create: `src/vidi/output.py`
- Create: `tests/test_output.py`

- [ ] **Step 1: Write failing tests for output**

Create `tests/test_output.py`:

```python
import json
from pathlib import Path

import pytest

from vidi.output import (
    extract_video_id,
    sanitize_filename,
    build_output_dir,
    write_file,
    file_exists,
    load_session,
    save_session,
)


class TestExtractVideoId:
    def test_standard_url(self):
        assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_short_url(self):
        assert extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_url_with_extra_params(self):
        assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=120") == "dQw4w9WgXcQ"

    def test_embed_url(self):
        assert extract_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_invalid_url_raises(self):
        with pytest.raises(ValueError, match="Could not extract video ID"):
            extract_video_id("https://example.com/notavideo")


class TestSanitizeFilename:
    def test_removes_unsafe_chars(self):
        assert sanitize_filename('Hello / World: "Test"') == "Hello  World Test"

    def test_collapses_whitespace(self):
        assert sanitize_filename("Hello    World") == "Hello World"

    def test_truncates_long_names(self):
        long_name = "A" * 200
        result = sanitize_filename(long_name)
        assert len(result) <= 80

    def test_handles_empty_string(self):
        assert sanitize_filename("") == "_"


class TestBuildOutputDir:
    def test_builds_correct_path(self, tmp_path):
        result = build_output_dir(
            title="My Video",
            creator="Some Channel",
            video_id="abc123",
            base_dir=tmp_path,
        )
        assert result == tmp_path / "vidi" / "My Video - Some Channel [abc123]"

    def test_sanitizes_names(self, tmp_path):
        result = build_output_dir(
            title='Bad/Name: "Here"',
            creator="Chan<nel>",
            video_id="xyz789",
            base_dir=tmp_path,
        )
        dirname = result.name
        assert "/" not in dirname
        assert ":" not in dirname
        assert "[xyz789]" in dirname


class TestWriteFile:
    def test_writes_content(self, tmp_path):
        path = tmp_path / "test.md"
        write_file(path, "hello world")
        assert path.read_text() == "hello world"

    def test_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "sub" / "dir" / "test.md"
        write_file(path, "content")
        assert path.read_text() == "content"


class TestFileExists:
    def test_returns_true_for_existing(self, tmp_path):
        path = tmp_path / "file.txt"
        path.write_text("data")
        assert file_exists(path) is True

    def test_returns_false_for_missing(self, tmp_path):
        path = tmp_path / "nope.txt"
        assert file_exists(path) is False


class TestSession:
    def test_save_and_load_session(self, tmp_path):
        session_file = tmp_path / ".session.json"
        data = {"history": [{"role": "user", "parts": ["hello"]}]}
        save_session(session_file, data)
        loaded = load_session(session_file)
        assert loaded == data

    def test_load_missing_session_returns_none(self, tmp_path):
        session_file = tmp_path / ".session.json"
        assert load_session(session_file) is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_output.py -v
```

Expected: ImportError — `vidi.output` does not exist.

- [ ] **Step 3: Implement `src/vidi/output.py`**

```python
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def extract_video_id(url: str) -> str:
    parsed = urlparse(url)
    if parsed.hostname in ("youtu.be",):
        video_id = parsed.path.lstrip("/")
        if video_id:
            return video_id.split("/")[0]
    if parsed.hostname in ("www.youtube.com", "youtube.com", "m.youtube.com"):
        if parsed.path == "/watch":
            qs = parse_qs(parsed.query)
            if "v" in qs:
                return qs["v"][0]
        if parsed.path.startswith("/embed/"):
            return parsed.path.split("/")[2]
        if parsed.path.startswith("/v/"):
            return parsed.path.split("/")[2]
    raise ValueError(f"Could not extract video ID from: {url}")


def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r'[/\\:*?"<>|]', "", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return "_"
    if len(cleaned) > 80:
        cleaned = cleaned[:80].rstrip()
    return cleaned


def build_output_dir(
    title: str,
    creator: str,
    video_id: str,
    base_dir: Path | None = None,
) -> Path:
    if base_dir is None:
        base_dir = Path.cwd()
    safe_title = sanitize_filename(title)
    safe_creator = sanitize_filename(creator)
    folder_name = f"{safe_title} - {safe_creator} [{video_id}]"
    return base_dir / "vidi" / folder_name


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def file_exists(path: Path) -> bool:
    return path.is_file()


def save_session(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_session(path: Path) -> dict | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_output.py -v
```

Expected: all 13 tests PASS.

- [ ] **Step 5: Run semgrep on output module**

```bash
semgrep --config auto src/vidi/output.py --json 2>/dev/null | python3 -m json.tool
```

Review findings. URL parsing uses `urlparse` (stdlib, safe). File writes use `Path.write_text` (no injection vector). Fix any real issues.

- [ ] **Step 6: Update progress.txt and commit**

```bash
git add src/vidi/output.py tests/test_output.py progress.txt
git commit -m "feat: add output module with path sanitization and file I/O"
```

---

### Task 4: Video Module (yt-dlp/ffmpeg wrappers)

**Files:**
- Create: `src/vidi/video.py`
- Create: `tests/test_video.py`

- [ ] **Step 1: Write failing tests for video**

Create `tests/test_video.py`:

```python
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from vidi.video import (
    check_dependency,
    get_install_instructions,
    download_captions,
    get_stream_url,
    extract_frame,
    parse_vtt_captions,
    format_timestamp,
)


class TestCheckDependency:
    def test_finds_existing_command(self):
        assert check_dependency("python3") is True

    def test_missing_command(self):
        assert check_dependency("nonexistent_binary_xyz") is False


class TestGetInstallInstructions:
    def test_ytdlp_instructions(self):
        instructions = get_install_instructions("yt-dlp")
        assert "pip install yt-dlp" in instructions

    def test_ffmpeg_instructions(self):
        instructions = get_install_instructions("ffmpeg")
        assert "ffmpeg" in instructions


class TestFormatTimestamp:
    def test_seconds_only(self):
        assert format_timestamp(45) == "0m45s"

    def test_minutes_and_seconds(self):
        assert format_timestamp(195) == "3m15s"

    def test_hours(self):
        assert format_timestamp(3661) == "61m01s"

    def test_zero(self):
        assert format_timestamp(0) == "0m00s"


class TestParseVttCaptions:
    def test_parses_vtt_content(self):
        vtt = """WEBVTT

00:00:01.000 --> 00:00:04.000
Hello everyone

00:00:05.000 --> 00:00:08.000
Welcome to the video
"""
        result = parse_vtt_captions(vtt)
        assert len(result) == 2
        assert result[0]["text"] == "Hello everyone"
        assert result[0]["start_seconds"] == 1

    def test_empty_vtt(self):
        result = parse_vtt_captions("WEBVTT\n\n")
        assert result == []


class TestDownloadCaptions:
    @patch("vidi.video.subprocess.run")
    def test_calls_ytdlp_with_list_args(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        download_captions("https://youtube.com/watch?v=abc123", Path("/tmp/out"))
        args = mock_run.call_args
        cmd = args[0][0]
        assert isinstance(cmd, list)
        assert "yt-dlp" in cmd[0]
        assert "https://youtube.com/watch?v=abc123" in cmd
        assert args[1].get("shell") is not True

    @patch("vidi.video.subprocess.run")
    def test_never_uses_shell(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        download_captions("https://youtube.com/watch?v=test", Path("/tmp/out"))
        assert mock_run.call_args[1].get("shell", False) is False


class TestGetStreamUrl:
    @patch("vidi.video.subprocess.run")
    def test_returns_url_from_stdout(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="https://r4---sn-example.googlevideo.com/videoplayback?id=123\n",
        )
        url = get_stream_url("https://youtube.com/watch?v=abc123")
        assert url.startswith("https://")
        cmd = mock_run.call_args[0][0]
        assert isinstance(cmd, list)

    @patch("vidi.video.subprocess.run")
    def test_raises_on_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        with pytest.raises(RuntimeError):
            get_stream_url("https://youtube.com/watch?v=abc123")


class TestExtractFrame:
    @patch("vidi.video.subprocess.run")
    def test_calls_ffmpeg_with_list_args(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        extract_frame("https://stream.url/video", 195, Path("/tmp/frames/3m15s.jpg"))
        cmd = mock_run.call_args[0][0]
        assert isinstance(cmd, list)
        assert "ffmpeg" in cmd[0]
        assert mock_run.call_args[1].get("shell", False) is False

    @patch("vidi.video.subprocess.run")
    def test_never_uses_shell(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        extract_frame("https://stream.url/video", 60, Path("/tmp/frames/1m00s.jpg"))
        assert mock_run.call_args[1].get("shell", False) is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_video.py -v
```

Expected: ImportError — `vidi.video` does not exist.

- [ ] **Step 3: Implement `src/vidi/video.py`**

```python
from __future__ import annotations

import platform
import re
import shutil
import subprocess
from pathlib import Path


def check_dependency(name: str) -> bool:
    return shutil.which(name) is not None


def get_install_instructions(name: str) -> str:
    system = platform.system().lower()
    if name == "yt-dlp":
        lines = [
            f"✗ {name} is not installed.\n",
            "Install it:",
            "  pip:    pip install yt-dlp",
        ]
        if system == "darwin":
            lines.append("  brew:   brew install yt-dlp")
        elif system == "linux":
            lines.append("  apt:    sudo apt install yt-dlp  (or pip install yt-dlp)")
        elif system == "windows":
            lines.append("  winget: winget install yt-dlp")
        lines.append("  docs:   https://github.com/yt-dlp/yt-dlp#installation")
        return "\n".join(lines)
    if name == "ffmpeg":
        lines = [
            f"✗ {name} is not installed.\n",
            "Install it:",
        ]
        if system == "darwin":
            lines.append("  brew:   brew install ffmpeg")
        elif system == "linux":
            lines.append("  apt:    sudo apt install ffmpeg")
        elif system == "windows":
            lines.append("  winget: winget install ffmpeg")
        lines.append("  docs:   https://ffmpeg.org/download.html")
        return "\n".join(lines)
    return f"✗ {name} is not installed."


def format_timestamp(seconds: int) -> str:
    m = seconds // 60
    s = seconds % 60
    return f"{m}m{s:02d}s"


def parse_vtt_captions(vtt_content: str) -> list[dict]:
    segments = []
    blocks = vtt_content.strip().split("\n\n")
    for block in blocks:
        lines = block.strip().split("\n")
        for i, line in enumerate(lines):
            match = re.match(r"(\d{2}):(\d{2}):(\d{2})\.\d+ --> ", line)
            if match:
                h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
                start_seconds = h * 3600 + m * 60 + s
                text_lines = lines[i + 1 :]
                text = " ".join(t.strip() for t in text_lines if t.strip())
                if text:
                    segments.append({"start_seconds": start_seconds, "text": text})
                break
    return segments


def download_captions(url: str, output_dir: Path) -> Path | None:
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "yt-dlp",
        "--write-auto-sub",
        "--write-sub",
        "--sub-lang", "en",
        "--sub-format", "vtt",
        "--skip-download",
        "--output", str(output_dir / "captions"),
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    vtt_files = list(output_dir.glob("captions*.vtt"))
    if vtt_files:
        return vtt_files[0]
    return None


def get_stream_url(url: str) -> str:
    cmd = [
        "yt-dlp",
        "--get-url",
        "--format", "best[ext=mp4]/best",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed to get stream URL: {result.stderr}")
    return result.stdout.strip().split("\n")[0]


def extract_frame(stream_url: str, seconds: int, output_path: Path) -> bool:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-ss", str(seconds),
        "-i", stream_url,
        "-frames:v", "1",
        "-q:v", "2",
        "-y",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_video.py -v
```

Expected: all 13 tests PASS.

- [ ] **Step 5: Run semgrep on video module — critical security check**

```bash
semgrep --config auto src/vidi/video.py --json 2>/dev/null | python3 -m json.tool
```

This is the highest-risk module. Verify:
- Every `subprocess.run` call uses a list (not a string) as the first argument
- No `shell=True` anywhere
- No f-string or `.format()` interpolation into command lists — URLs and paths are passed as standalone list elements
- `capture_output=True` is used (prevents output leaking to terminal)

Fix any findings before proceeding.

- [ ] **Step 6: Update progress.txt and commit**

```bash
git add src/vidi/video.py tests/test_video.py progress.txt
git commit -m "feat: add video module with yt-dlp/ffmpeg wrappers"
```

---

### Task 5: Gemini Module

**Files:**
- Create: `src/vidi/gemini.py`
- Create: `tests/test_gemini.py`

- [ ] **Step 1: Write failing tests for gemini**

Create `tests/test_gemini.py`:

```python
import json
from unittest.mock import patch, MagicMock

import pytest

from vidi.gemini import (
    build_summary_prompt,
    build_timestamps_prompt,
    build_transcript_prompt,
    parse_timestamps_response,
    parse_transcript_response,
    format_summary_md,
    format_transcript_md,
    create_client,
)


class TestPrompts:
    def test_summary_prompt_contains_url(self):
        prompt = build_summary_prompt("https://youtube.com/watch?v=abc")
        assert "https://youtube.com/watch?v=abc" in prompt

    def test_timestamps_prompt_contains_url(self):
        prompt = build_timestamps_prompt("https://youtube.com/watch?v=abc")
        assert "https://youtube.com/watch?v=abc" in prompt

    def test_transcript_prompt_contains_url(self):
        prompt = build_transcript_prompt("https://youtube.com/watch?v=abc")
        assert "https://youtube.com/watch?v=abc" in prompt


class TestParseTimestampsResponse:
    def test_parses_json_from_response(self):
        response_text = """Here are the key timestamps:
```json
[
  {"time": "1:30", "seconds": 90, "label": "intro ends", "type": "topic"},
  {"time": "5:00", "seconds": 300, "label": "demo starts", "type": "visual"}
]
```"""
        result = parse_timestamps_response(response_text)
        assert len(result) == 2
        assert result[0]["seconds"] == 90
        assert result[1]["type"] == "visual"

    def test_parses_raw_json_response(self):
        response_text = '[{"time": "0:30", "seconds": 30, "label": "start", "type": "topic"}]'
        result = parse_timestamps_response(response_text)
        assert len(result) == 1

    def test_raises_on_invalid_response(self):
        with pytest.raises(ValueError, match="Could not parse timestamps"):
            parse_timestamps_response("no json here at all")


class TestParseTranscriptResponse:
    def test_parses_transcript_lines(self):
        response_text = """[0:00] Hello everyone
[0:15] Welcome to the video
[1:30] Let's get started"""
        result = parse_transcript_response(response_text)
        assert len(result) == 3
        assert result[0]["text"] == "Hello everyone"

    def test_returns_raw_if_no_timestamps(self):
        response_text = "This is just a plain transcript without timestamps."
        result = parse_transcript_response(response_text)
        assert len(result) == 1
        assert result[0]["text"] == response_text


class TestFormatSummaryMd:
    def test_formats_complete_summary(self):
        result = format_summary_md(
            title="Test Video",
            creator="Test Channel",
            duration="10:30",
            url="https://youtube.com/watch?v=abc",
            overview="This is a test video.",
            key_points=["Point one", "Point two"],
            conclusions="The video concludes with a summary.",
        )
        assert "# Test Video" in result
        assert "**Creator:** Test Channel" in result
        assert "## Overview" in result
        assert "- Point one" in result
        assert "## Conclusions" in result


class TestFormatTranscriptMd:
    def test_formats_segments(self):
        segments = [
            {"start_seconds": 0, "text": "Hello"},
            {"start_seconds": 75, "text": "World"},
        ]
        result = format_transcript_md(segments)
        assert "[0:00]" in result
        assert "[1:15]" in result
        assert "Hello" in result


class TestCreateClient:
    @patch("vidi.gemini.genai")
    def test_creates_client_with_key(self, mock_genai):
        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model
        client = create_client("test-key")
        mock_genai.configure.assert_called_once_with(api_key="test-key")
        assert client is mock_model
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_gemini.py -v
```

Expected: ImportError — `vidi.gemini` does not exist.

- [ ] **Step 3: Implement `src/vidi/gemini.py`**

```python
from __future__ import annotations

import json
import re

import google.generativeai as genai


def create_client(api_key: str, model_name: str = "gemini-2.0-flash") -> genai.GenerativeModel:
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name)


def build_summary_prompt(url: str) -> str:
    return f"""Analyze this YouTube video: {url}

Provide a structured analysis with these exact sections:

TITLE: The video title
CREATOR: The channel/creator name
DURATION: The video duration in HH:MM:SS or MM:SS format

OVERVIEW:
Two to three sentences describing what this video is about.

KEY POINTS:
- First key point with context
- Second key point with context
- Third key point with context
(Include as many key points as appropriate)

CONCLUSIONS:
What the video concludes or recommends."""


def build_timestamps_prompt(url: str) -> str:
    return f"""Analyze this YouTube video: {url}

Identify the key moments/timestamps in this video. For each moment, provide:
- time: the timestamp in M:SS or H:MM:SS format
- seconds: the total seconds from start
- label: a brief description of what happens at this moment
- type: one of "visual" (slide, diagram, demo shown), "topic" (new subject introduced), or "key_point" (important statement made)

Return the results as a JSON array. Example format:
```json
[
  {{"time": "1:30", "seconds": 90, "label": "introduces the main concept", "type": "topic"}},
  {{"time": "3:45", "seconds": 225, "label": "shows architecture diagram", "type": "visual"}}
]
```

Return ONLY the JSON array, no other text."""


def build_transcript_prompt(url: str) -> str:
    return f"""Transcribe this YouTube video: {url}

Provide a timestamped transcript in this exact format:
[M:SS] Text spoken at this timestamp
[M:SS] Next line of dialogue

Include timestamps at natural speech boundaries (every 10-30 seconds).
Return ONLY the transcript lines, no other text."""


def parse_timestamps_response(response_text: str) -> list[dict]:
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", response_text, re.DOTALL)
    if json_match:
        return json.loads(json_match.group(1))
    try:
        result = json.loads(response_text.strip())
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass
    raise ValueError(f"Could not parse timestamps from response: {response_text[:200]}")


def parse_transcript_response(response_text: str) -> list[dict]:
    lines = response_text.strip().split("\n")
    segments = []
    pattern = re.compile(r"\[(\d+):(\d{2})\]\s*(.*)")
    for line in lines:
        match = pattern.match(line.strip())
        if match:
            minutes, seconds, text = int(match.group(1)), int(match.group(2)), match.group(3)
            segments.append({
                "start_seconds": minutes * 60 + seconds,
                "text": text,
            })
    if not segments:
        return [{"start_seconds": 0, "text": response_text.strip()}]
    return segments


def format_summary_md(
    title: str,
    creator: str,
    duration: str,
    url: str,
    overview: str,
    key_points: list[str],
    conclusions: str,
) -> str:
    points = "\n".join(f"- {p}" for p in key_points)
    return f"""# {title}
**Creator:** {creator}
**Duration:** {duration}
**URL:** {url}

## Overview
{overview}

## Key Points
{points}

## Conclusions
{conclusions}
"""


def format_transcript_md(segments: list[dict]) -> str:
    lines = []
    for seg in segments:
        total = seg["start_seconds"]
        m, s = divmod(total, 60)
        lines.append(f"[{m}:{s:02d}] {seg['text']}")
    return "\n".join(lines) + "\n"


def parse_summary_response(response_text: str) -> dict:
    result = {
        "title": "",
        "creator": "",
        "duration": "",
        "overview": "",
        "key_points": [],
        "conclusions": "",
    }
    current_section = None
    lines = response_text.strip().split("\n")

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("TITLE:"):
            result["title"] = stripped[6:].strip()
        elif stripped.startswith("CREATOR:"):
            result["creator"] = stripped[8:].strip()
        elif stripped.startswith("DURATION:"):
            result["duration"] = stripped[9:].strip()
        elif stripped == "OVERVIEW:":
            current_section = "overview"
        elif stripped == "KEY POINTS:":
            current_section = "key_points"
        elif stripped == "CONCLUSIONS:":
            current_section = "conclusions"
        elif current_section == "overview" and stripped:
            if result["overview"]:
                result["overview"] += " " + stripped
            else:
                result["overview"] = stripped
        elif current_section == "key_points" and stripped.startswith("- "):
            result["key_points"].append(stripped[2:])
        elif current_section == "conclusions" and stripped:
            if result["conclusions"]:
                result["conclusions"] += " " + stripped
            else:
                result["conclusions"] = stripped

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_gemini.py -v
```

Expected: all 12 tests PASS.

- [ ] **Step 5: Run semgrep on gemini module**

```bash
semgrep --config auto src/vidi/gemini.py --json 2>/dev/null | python3 -m json.tool
```

Review findings. The prompts contain user-provided URLs but they go to Gemini's API (not a shell). The `json.loads` calls parse Gemini responses, not raw user input. Fix any real issues.

- [ ] **Step 6: Update progress.txt and commit**

```bash
git add src/vidi/gemini.py tests/test_gemini.py progress.txt
git commit -m "feat: add gemini module with prompts and response parsing"
```

---

### Task 6: CLI Commands — config, summarize, timestamps

**Files:**
- Modify: `src/vidi/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests for CLI commands**

Create `tests/test_cli.py`:

```python
from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest
from typer.testing import CliRunner

from vidi.cli import app

runner = CliRunner()


class TestConfigCommands:
    @patch("vidi.cli.get_config_path")
    def test_config_path(self, mock_path):
        mock_path.return_value = Path("/home/test/.config/vidi/config.toml")
        result = runner.invoke(app, ["config", "path"])
        assert result.exit_code == 0
        assert "/home/test/.config/vidi/config.toml" in result.output

    @patch("vidi.cli.load_config")
    @patch("vidi.cli.get_api_key")
    def test_config_show(self, mock_key, mock_config):
        mock_key.return_value = "abcdefghij"
        mock_config.return_value = {"api": {"gemini_key": "abcdefghij"}}
        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "abcd...ghij" in result.output

    @patch("vidi.cli.save_config")
    def test_config_set(self, mock_save):
        result = runner.invoke(app, ["config", "set", "gemini_key", "new-key"])
        assert result.exit_code == 0
        mock_save.assert_called_once_with("gemini_key", "new-key")


class TestSummarizeCommand:
    @patch("vidi.cli.file_exists", return_value=False)
    @patch("vidi.cli.get_api_key", return_value="test-key")
    @patch("vidi.cli.create_client")
    @patch("vidi.cli.extract_video_id", return_value="abc123")
    @patch("vidi.cli.build_output_dir")
    def test_summarize_calls_gemini(
        self, mock_dir, mock_id, mock_client, mock_key, mock_exists
    ):
        mock_dir.return_value = Path("/tmp/vidi/Test [abc123]")
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = """TITLE: Test Video
CREATOR: Test Channel
DURATION: 10:30

OVERVIEW:
This is a test video about testing.

KEY POINTS:
- First point
- Second point

CONCLUSIONS:
Testing is important."""
        mock_model.generate_content.return_value = mock_response
        mock_client.return_value = mock_model

        with patch("vidi.cli.write_file") as mock_write:
            result = runner.invoke(app, ["summarize", "https://youtube.com/watch?v=abc123"])
        assert result.exit_code == 0

    @patch("vidi.cli.file_exists", return_value=True)
    @patch("vidi.cli.get_api_key", return_value="test-key")
    @patch("vidi.cli.extract_video_id", return_value="abc123")
    @patch("vidi.cli.build_output_dir")
    def test_summarize_skips_existing(self, mock_dir, mock_id, mock_key, mock_exists):
        mock_dir.return_value = Path("/tmp/vidi/Test [abc123]")
        result = runner.invoke(app, ["summarize", "https://youtube.com/watch?v=abc123"])
        assert result.exit_code == 0
        assert "exists" in result.output.lower() or "skip" in result.output.lower()


class TestTimestampsCommand:
    @patch("vidi.cli.file_exists", return_value=False)
    @patch("vidi.cli.get_api_key", return_value="test-key")
    @patch("vidi.cli.create_client")
    @patch("vidi.cli.extract_video_id", return_value="abc123")
    @patch("vidi.cli.build_output_dir")
    def test_timestamps_writes_json(
        self, mock_dir, mock_id, mock_client, mock_key, mock_exists
    ):
        mock_dir.return_value = Path("/tmp/vidi/Test [abc123]")
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '[{"time": "1:30", "seconds": 90, "label": "intro", "type": "topic"}]'
        mock_model.generate_content.return_value = mock_response
        mock_client.return_value = mock_model

        with patch("vidi.cli.write_file") as mock_write:
            result = runner.invoke(app, ["timestamps", "https://youtube.com/watch?v=abc123"])
        assert result.exit_code == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_cli.py -v
```

Expected: failures — CLI commands not yet defined.

- [ ] **Step 3: Implement CLI commands in `src/vidi/cli.py`**

Replace `src/vidi/cli.py` with:

```python
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer

from vidi.config import get_api_key, get_config_path, load_config, save_config, mask_key
from vidi.gemini import (
    build_summary_prompt,
    build_timestamps_prompt,
    create_client,
    format_summary_md,
    parse_summary_response,
    parse_timestamps_response,
)
from vidi.output import (
    build_output_dir,
    extract_video_id,
    file_exists,
    write_file,
)

app = typer.Typer(
    name="vidi",
    help="YouTube video analyzer powered by Google Gemini.",
    add_completion=False,
)
config_app = typer.Typer(help="Manage API keys and settings.")
app.add_typer(config_app, name="config")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


# --- Config commands ---


@config_app.command("path")
def config_path() -> None:
    """Print the config file path."""
    typer.echo(get_config_path())


@config_app.command("show")
def config_show() -> None:
    """Show current configuration (keys masked)."""
    key = get_api_key(prompt_if_missing=False)
    typer.echo(f"gemini_key: {mask_key(key)}")
    config = load_config()
    yt_key = config.get("api", {}).get("youtube_key")
    if yt_key:
        typer.echo(f"youtube_key: {mask_key(yt_key)}")


@config_app.command("set")
def config_set(key: str, value: str) -> None:
    """Set a configuration value."""
    save_config(key, value)
    typer.echo(f"✓ {key} updated")


# --- Helper to get video output dir ---


def _resolve_output_dir(url: str, model: object) -> tuple[Path, str]:
    """Get or create the output directory for a video. Returns (output_dir, video_id)."""
    video_id = extract_video_id(url)
    # Try to get title/creator from a quick Gemini call
    response = model.generate_content(
        f"For this YouTube video: {url}\n\nReturn ONLY two lines:\nTITLE: the video title\nCREATOR: the channel name"
    )
    title, creator = video_id, "Unknown"
    for line in response.text.strip().split("\n"):
        if line.startswith("TITLE:"):
            title = line[6:].strip()
        elif line.startswith("CREATOR:"):
            creator = line[8:].strip()
    output_dir = build_output_dir(title, creator, video_id)
    return output_dir, video_id


def _require_api_key() -> str:
    """Get API key or exit with error."""
    key = get_api_key()
    if not key:
        typer.echo("✗ No Gemini API key configured. Run: vidi config set gemini_key YOUR_KEY", err=True)
        raise typer.Exit(1)
    return key


# --- Gemini commands ---


@app.command()
def summarize(
    url: str = typer.Argument(help="YouTube video URL"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing output"),
) -> None:
    """Summarize a YouTube video."""
    key = _require_api_key()
    model = create_client(key)
    output_dir, video_id = _resolve_output_dir(url, model)
    summary_path = output_dir / "summary.md"

    if file_exists(summary_path) and not force:
        typer.echo(f"✓ summary.md already exists (use --force to overwrite)")
        return

    typer.echo("Analyzing video...")
    prompt = build_summary_prompt(url)
    response = model.generate_content(prompt)
    parsed = parse_summary_response(response.text)
    md = format_summary_md(
        title=parsed["title"] or video_id,
        creator=parsed["creator"] or "Unknown",
        duration=parsed["duration"] or "Unknown",
        url=url,
        overview=parsed["overview"],
        key_points=parsed["key_points"],
        conclusions=parsed["conclusions"],
    )
    write_file(summary_path, md)
    typer.echo(f"✓ summary.md")


@app.command()
def timestamps(
    url: str = typer.Argument(help="YouTube video URL"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing output"),
) -> None:
    """Extract key moments from a YouTube video."""
    key = _require_api_key()
    model = create_client(key)
    output_dir, video_id = _resolve_output_dir(url, model)
    timestamps_path = output_dir / "timestamps.json"

    if file_exists(timestamps_path) and not force:
        typer.echo(f"✓ timestamps.json already exists (use --force to overwrite)")
        return

    typer.echo("Identifying key moments...")
    prompt = build_timestamps_prompt(url)
    response = model.generate_content(prompt)
    ts_data = parse_timestamps_response(response.text)

    # Add frame filenames
    from vidi.video import format_timestamp
    for entry in ts_data:
        entry["frame"] = f"{format_timestamp(entry['seconds'])}.jpg"

    write_file(timestamps_path, json.dumps(ts_data, indent=2) + "\n")
    typer.echo(f"✓ timestamps.json ({len(ts_data)} moments)")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_cli.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Run semgrep on CLI module**

```bash
semgrep --config auto src/vidi/cli.py --json 2>/dev/null | python3 -m json.tool
```

- [ ] **Step 6: Update progress.txt and commit**

```bash
git add src/vidi/cli.py tests/test_cli.py progress.txt
git commit -m "feat: add config, summarize, timestamps CLI commands"
```

---

### Task 7: CLI Commands — transcript, frames, ask

**Files:**
- Modify: `src/vidi/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests for transcript, frames, ask**

Append to `tests/test_cli.py`:

```python
class TestTranscriptCommand:
    @patch("vidi.cli.file_exists", return_value=False)
    @patch("vidi.cli.get_api_key", return_value="test-key")
    @patch("vidi.cli.create_client")
    @patch("vidi.cli.extract_video_id", return_value="abc123")
    @patch("vidi.cli.build_output_dir")
    @patch("vidi.cli.check_dependency", return_value=True)
    @patch("vidi.cli.download_captions")
    def test_transcript_uses_ytdlp(
        self, mock_dl, mock_dep, mock_dir, mock_id, mock_client, mock_key, mock_exists
    ):
        mock_dir.return_value = Path("/tmp/vidi/Test [abc123]")
        mock_model = MagicMock()
        mock_model.generate_content.return_value = MagicMock(
            text="TITLE: Test\nCREATOR: Chan"
        )
        mock_client.return_value = mock_model
        vtt_file = Path("/tmp/captions.en.vtt")
        mock_dl.return_value = vtt_file

        with patch("builtins.open", MagicMock()):
            with patch.object(Path, "read_text", return_value="WEBVTT\n\n00:00:01.000 --> 00:00:04.000\nHello\n"):
                with patch("vidi.cli.write_file"):
                    result = runner.invoke(app, ["transcript", "https://youtube.com/watch?v=abc123"])
        assert result.exit_code == 0


class TestAskCommand:
    @patch("vidi.cli.load_session", return_value=None)
    @patch("vidi.cli.get_api_key", return_value="test-key")
    @patch("vidi.cli.create_client")
    @patch("vidi.cli.extract_video_id", return_value="abc123")
    @patch("vidi.cli.build_output_dir")
    def test_ask_prints_answer(
        self, mock_dir, mock_id, mock_client, mock_key, mock_session
    ):
        mock_dir.return_value = Path("/tmp/vidi/Test [abc123]")
        mock_model = MagicMock()
        # First call: title/creator resolution
        # Second call: the actual question
        mock_model.generate_content.side_effect = [
            MagicMock(text="TITLE: Test\nCREATOR: Chan"),
            MagicMock(text="The video discusses React 19."),
        ]
        mock_model.start_chat.return_value = MagicMock(
            send_message=MagicMock(return_value=MagicMock(text="The video discusses React 19.")),
            history=[],
        )
        mock_client.return_value = mock_model

        with patch("vidi.cli.save_session"):
            result = runner.invoke(app, ["ask", "https://youtube.com/watch?v=abc123", "What framework?"])
        assert result.exit_code == 0
        assert "React" in result.output


class TestFramesCommand:
    @patch("vidi.cli.file_exists")
    @patch("vidi.cli.get_api_key", return_value="test-key")
    @patch("vidi.cli.create_client")
    @patch("vidi.cli.extract_video_id", return_value="abc123")
    @patch("vidi.cli.build_output_dir")
    @patch("vidi.cli.check_dependency", return_value=True)
    @patch("vidi.cli.get_stream_url", return_value="https://stream.url/video")
    @patch("vidi.cli.extract_frame", return_value=True)
    def test_frames_extracts_from_timestamps(
        self, mock_extract, mock_stream, mock_dep, mock_dir, mock_id, mock_client, mock_key, mock_exists
    ):
        mock_dir.return_value = Path("/tmp/vidi/Test [abc123]")
        mock_model = MagicMock()
        mock_model.generate_content.return_value = MagicMock(
            text="TITLE: Test\nCREATOR: Chan"
        )
        mock_client.return_value = mock_model

        # frames/ doesn't exist, but timestamps.json does
        def exists_side_effect(path):
            if "timestamps.json" in str(path):
                return True
            return False
        mock_exists.side_effect = exists_side_effect

        ts_data = json.dumps([
            {"time": "1:30", "seconds": 90, "label": "intro", "type": "topic", "frame": "1m30s.jpg"}
        ])
        with patch.object(Path, "read_text", return_value=ts_data):
            result = runner.invoke(app, ["frames", "https://youtube.com/watch?v=abc123", "--force"])
        assert result.exit_code == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_cli.py -v
```

Expected: failures on the new test classes.

- [ ] **Step 3: Add transcript, frames, ask commands to `src/vidi/cli.py`**

Append to `src/vidi/cli.py`:

```python
from vidi.gemini import (
    build_transcript_prompt,
    format_transcript_md,
    parse_transcript_response,
)
from vidi.output import load_session, save_session
from vidi.video import (
    check_dependency,
    download_captions,
    extract_frame,
    format_timestamp,
    get_install_instructions,
    get_stream_url,
    parse_vtt_captions,
)


@app.command()
def transcript(
    url: str = typer.Argument(help="YouTube video URL"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing output"),
) -> None:
    """Get video transcript (captions or Gemini fallback)."""
    key = _require_api_key()
    model = create_client(key)
    output_dir, video_id = _resolve_output_dir(url, model)
    transcript_path = output_dir / "transcript.md"

    if file_exists(transcript_path) and not force:
        typer.echo("✓ transcript.md already exists (use --force to overwrite)")
        return

    segments = None

    # Try yt-dlp captions first
    if check_dependency("yt-dlp"):
        typer.echo("Downloading captions...")
        vtt_path = download_captions(url, output_dir / ".tmp_captions")
        if vtt_path:
            vtt_content = vtt_path.read_text(encoding="utf-8")
            segments = parse_vtt_captions(vtt_content)
    else:
        typer.echo("yt-dlp not found — using Gemini transcription as fallback")

    # Fallback to Gemini transcription
    if not segments:
        typer.echo("Transcribing with Gemini...")
        prompt = build_transcript_prompt(url)
        response = model.generate_content(prompt)
        segments = parse_transcript_response(response.text)

    md = format_transcript_md(segments)
    write_file(transcript_path, md)
    typer.echo("✓ transcript.md")


@app.command()
def frames(
    url: str = typer.Argument(help="YouTube video URL"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing output"),
) -> None:
    """Extract frames at key timestamps."""
    key = _require_api_key()

    # Check dependencies
    for dep in ("yt-dlp", "ffmpeg"):
        if not check_dependency(dep):
            typer.echo(get_install_instructions(dep), err=True)
            raise typer.Exit(1)

    model = create_client(key)
    output_dir, video_id = _resolve_output_dir(url, model)
    frames_dir = output_dir / "frames"
    timestamps_path = output_dir / "timestamps.json"

    # Need timestamps first
    if not file_exists(timestamps_path):
        typer.echo("Generating timestamps first...")
        prompt = build_timestamps_prompt(url)
        response = model.generate_content(prompt)
        ts_data = parse_timestamps_response(response.text)
        for entry in ts_data:
            entry["frame"] = f"{format_timestamp(entry['seconds'])}.jpg"
        write_file(timestamps_path, json.dumps(ts_data, indent=2) + "\n")
    else:
        ts_data = json.loads(timestamps_path.read_text(encoding="utf-8"))

    if not ts_data:
        typer.echo("No timestamps found — nothing to extract.")
        return

    typer.echo("Getting stream URL...")
    stream_url = get_stream_url(url)

    extracted = 0
    for entry in ts_data:
        frame_path = frames_dir / entry["frame"]
        if file_exists(frame_path) and not force:
            extracted += 1
            continue
        if extract_frame(stream_url, entry["seconds"], frame_path):
            extracted += 1
        else:
            typer.echo(f"  ✗ failed: {entry['frame']}", err=True)

    typer.echo(f"✓ frames/ ({extracted} frames)")


@app.command()
def ask(
    url: str = typer.Argument(help="YouTube video URL"),
    question: str = typer.Argument(help="Question about the video"),
    new: bool = typer.Option(False, "--new", help="Start a fresh session"),
) -> None:
    """Ask a question about a YouTube video."""
    key = _require_api_key()
    model = create_client(key)
    output_dir, video_id = _resolve_output_dir(url, model)
    session_path = output_dir / ".session.json"

    if new and session_path.exists():
        session_path.unlink()

    session_data = load_session(session_path)

    if session_data and session_data.get("history"):
        # Resume existing chat
        chat = model.start_chat(history=session_data["history"])
    else:
        # New chat with video context
        chat = model.start_chat(history=[])
        chat.send_message(f"I want to ask questions about this YouTube video: {url}")

    response = chat.send_message(question)
    typer.echo(response.text)

    save_session(session_path, {
        "video_url": url,
        "video_id": video_id,
        "history": [{"role": m.role, "parts": [p.text for p in m.parts]} for m in chat.history],
    })
```

- [ ] **Step 4: Consolidate imports at top of `cli.py`**

Make sure all imports are at the top of the file, not duplicated. The final import block should be:

```python
from vidi.config import get_api_key, get_config_path, load_config, save_config, mask_key
from vidi.gemini import (
    build_summary_prompt,
    build_timestamps_prompt,
    build_transcript_prompt,
    create_client,
    format_summary_md,
    format_transcript_md,
    parse_summary_response,
    parse_timestamps_response,
    parse_transcript_response,
)
from vidi.output import (
    build_output_dir,
    extract_video_id,
    file_exists,
    load_session,
    save_session,
    write_file,
)
from vidi.video import (
    check_dependency,
    download_captions,
    extract_frame,
    format_timestamp,
    get_install_instructions,
    get_stream_url,
    parse_vtt_captions,
)
```

- [ ] **Step 5: Run all tests**

```bash
uv run pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 6: Run semgrep on full CLI**

```bash
semgrep --config auto src/vidi/cli.py --json 2>/dev/null | python3 -m json.tool
```

- [ ] **Step 7: Update progress.txt and commit**

```bash
git add src/vidi/cli.py tests/test_cli.py progress.txt
git commit -m "feat: add transcript, frames, ask CLI commands"
```

---

### Task 8: CLI Command — analyze (orchestrator)

**Files:**
- Modify: `src/vidi/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing test for analyze**

Append to `tests/test_cli.py`:

```python
class TestAnalyzeCommand:
    @patch("vidi.cli.check_dependency", return_value=True)
    @patch("vidi.cli.get_api_key", return_value="test-key")
    @patch("vidi.cli.create_client")
    @patch("vidi.cli.extract_video_id", return_value="abc123")
    @patch("vidi.cli.build_output_dir")
    def test_analyze_runs_all_steps(
        self, mock_dir, mock_id, mock_client, mock_key, mock_dep
    ):
        mock_dir.return_value = Path("/tmp/vidi/Test [abc123]")
        mock_model = MagicMock()
        # Title resolution + summarize + timestamps + transcript fallback
        mock_model.generate_content.side_effect = [
            MagicMock(text="TITLE: Test\nCREATOR: Chan"),
            MagicMock(text="TITLE: Test\nCREATOR: Chan\nDURATION: 10:00\n\nOVERVIEW:\nA test.\n\nKEY POINTS:\n- Point\n\nCONCLUSIONS:\nDone."),
            MagicMock(text='[{"time": "1:30", "seconds": 90, "label": "intro", "type": "topic"}]'),
            MagicMock(text="[0:00] Hello world"),
        ]
        mock_client.return_value = mock_model

        with patch("vidi.cli.write_file"):
            with patch("vidi.cli.file_exists", return_value=False):
                with patch("vidi.cli.download_captions", return_value=None):
                    with patch("vidi.cli.get_stream_url", return_value="https://stream.url"):
                        with patch("vidi.cli.extract_frame", return_value=True):
                            result = runner.invoke(app, ["analyze", "https://youtube.com/watch?v=abc123"])

        assert result.exit_code == 0
        assert "summary" in result.output.lower()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_cli.py::TestAnalyzeCommand -v
```

Expected: failure — `analyze` command not defined.

- [ ] **Step 3: Implement analyze command in `src/vidi/cli.py`**

Add to `src/vidi/cli.py`:

```python
@app.command()
def analyze(
    url: str = typer.Argument(help="YouTube video URL"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing output"),
) -> None:
    """Run full analysis: summarize, timestamps, transcript, frames."""
    key = _require_api_key()
    model = create_client(key)
    output_dir, video_id = _resolve_output_dir(url, model)

    results = []

    # Step 1: Summarize
    try:
        summary_path = output_dir / "summary.md"
        if file_exists(summary_path) and not force:
            results.append(("summary.md", True, "already exists"))
        else:
            response = model.generate_content(build_summary_prompt(url))
            parsed = parse_summary_response(response.text)
            md = format_summary_md(
                title=parsed["title"] or video_id,
                creator=parsed["creator"] or "Unknown",
                duration=parsed["duration"] or "Unknown",
                url=url,
                overview=parsed["overview"],
                key_points=parsed["key_points"],
                conclusions=parsed["conclusions"],
            )
            write_file(summary_path, md)
            results.append(("summary.md", True, None))
    except Exception as e:
        results.append(("summary.md", False, str(e)))

    # Step 2: Timestamps
    timestamps_path = output_dir / "timestamps.json"
    ts_data = []
    try:
        if file_exists(timestamps_path) and not force:
            ts_data = json.loads(timestamps_path.read_text(encoding="utf-8"))
            results.append(("timestamps.json", True, "already exists"))
        else:
            response = model.generate_content(build_timestamps_prompt(url))
            ts_data = parse_timestamps_response(response.text)
            for entry in ts_data:
                entry["frame"] = f"{format_timestamp(entry['seconds'])}.jpg"
            write_file(timestamps_path, json.dumps(ts_data, indent=2) + "\n")
            results.append(("timestamps.json", True, f"{len(ts_data)} moments"))
    except Exception as e:
        results.append(("timestamps.json", False, str(e)))

    # Step 3: Transcript
    try:
        transcript_path = output_dir / "transcript.md"
        if file_exists(transcript_path) and not force:
            results.append(("transcript.md", True, "already exists"))
        else:
            segments = None
            if check_dependency("yt-dlp"):
                vtt_path = download_captions(url, output_dir / ".tmp_captions")
                if vtt_path:
                    vtt_content = vtt_path.read_text(encoding="utf-8")
                    segments = parse_vtt_captions(vtt_content)
            if not segments:
                response = model.generate_content(build_transcript_prompt(url))
                segments = parse_transcript_response(response.text)
            md = format_transcript_md(segments)
            write_file(transcript_path, md)
            results.append(("transcript.md", True, None))
    except Exception as e:
        results.append(("transcript.md", False, str(e)))

    # Step 4: Frames
    try:
        if not ts_data:
            results.append(("frames/", False, "no timestamps available"))
        elif not check_dependency("yt-dlp") or not check_dependency("ffmpeg"):
            results.append(("frames/", False, "yt-dlp or ffmpeg not installed"))
        else:
            stream_url = get_stream_url(url)
            frames_dir = output_dir / "frames"
            extracted = 0
            for entry in ts_data:
                frame_path = frames_dir / entry["frame"]
                if file_exists(frame_path) and not force:
                    extracted += 1
                    continue
                if extract_frame(stream_url, entry["seconds"], frame_path):
                    extracted += 1
            results.append(("frames/", True, f"{extracted} frames"))
    except Exception as e:
        results.append(("frames/", False, str(e)))

    # Report
    typer.echo(f"\nOutput: {output_dir}\n")
    any_failed = False
    for name, success, detail in results:
        if success:
            msg = f"✓ {name}"
            if detail:
                msg += f" ({detail})"
            typer.echo(msg)
        else:
            typer.echo(f"✗ {name} — {detail}", err=True)
            any_failed = True

    if any_failed:
        raise typer.Exit(1)
```

- [ ] **Step 4: Run all tests**

```bash
uv run pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 5: Update progress.txt and commit**

```bash
git add src/vidi/cli.py tests/test_cli.py progress.txt
git commit -m "feat: add analyze command with partial-failure handling"
```

---

### Task 9: Full Security Audit

**Files:**
- Review: all files in `src/vidi/`

- [ ] **Step 1: Run semgrep on entire project**

```bash
semgrep --config auto src/vidi/ --json 2>/dev/null | python3 -m json.tool
```

- [ ] **Step 2: Manual subprocess audit**

Check every `subprocess.run` call in `src/vidi/video.py`:

1. First argument is a list, not a string
2. No `shell=True` keyword
3. No f-string or `.format()` inside the command list elements that include user input
4. `capture_output=True` is present
5. URLs are passed as standalone list elements

For each call, note: "PASS — list args, no shell, no interpolation" or describe the issue found.

- [ ] **Step 3: Manual input validation audit**

Check:
1. `extract_video_id` — does it validate the URL structure before extracting?
2. `sanitize_filename` — does it catch all filesystem-unsafe characters?
3. `config.py` — does `save_config` escape/validate values written to TOML?
4. `gemini.py` — are URLs passed to Gemini prompts (not to shells)?

For each check, note PASS or describe the issue.

- [ ] **Step 4: Fix any findings**

If semgrep or manual review finds real issues, fix them. If a finding is a false positive, document why.

- [ ] **Step 5: Run full test suite after fixes**

```bash
uv run pytest tests/ -v
```

Expected: all tests still PASS.

- [ ] **Step 6: Update progress.txt and commit**

```bash
git add -A
git commit -m "security: audit and fix semgrep/manual findings"
```

---

### Task 10: Code Review and Final Polish

**Files:**
- Review: all files in `src/vidi/` and `tests/`

- [ ] **Step 1: Run code review agent**

Use the `superpowers:code-reviewer` agent to review the full implementation against the design spec at `docs/superpowers/specs/2026-04-02-vidi-design.md`.

- [ ] **Step 2: Fix issues found in review**

Address each issue. For non-issues, comment why they're not issues.

- [ ] **Step 3: Run full test suite after fixes**

```bash
uv run pytest tests/ -v
```

- [ ] **Step 4: Run semgrep one final time**

```bash
semgrep --config auto src/vidi/ --json 2>/dev/null | python3 -m json.tool
```

- [ ] **Step 5: Verify CLI works end-to-end**

```bash
vidi --help
vidi config path
vidi summarize --help
vidi analyze --help
```

Expected: all commands show correct help text.

- [ ] **Step 6: Update progress.txt with final status and commit**

```bash
git add -A
git commit -m "chore: code review fixes and final polish"
```

- [ ] **Step 7: Repeat review/fix cycle if issues remain**

If the code review found issues that needed fixing, run the review again. Continue until clean. Each cycle gets its own commit.
