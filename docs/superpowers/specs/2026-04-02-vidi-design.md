# vidi — YouTube Video Analyzer CLI

## Purpose

A Python CLI tool that sends YouTube URLs to Google's Gemini API for video analysis and writes structured output to a local `vidi/` folder in the current working directory. Designed for both human consumption and automated use by a Claude Code companion skill.

**Origin:** Reimagines the yt-analysis-mcp server (github.com/Legorobotdude/yt-analysis-mcp) as a file-based CLI. The MCP server works but couples analysis to an MCP session. vidi produces persistent files on disk that can be referenced across conversations, committed alongside project work, and consumed by any tool.

## Architecture

```
src/vidi/
  __init__.py       ← package root, version
  cli.py            ← typer app, command definitions, output formatting
  gemini.py         ← Gemini API client, chat session management, prompt templates
  video.py          ← yt-dlp/ffmpeg subprocess wrappers (list args, no shell)
  output.py         ← folder creation, path sanitization, file writing
  config.py         ← env var / config.toml lookup chain, first-run setup
```

**Layer responsibilities:**

- `cli.py` — Parses args, calls into gemini/video/output layers, formats terminal output (progress, success/failure). No business logic.
- `gemini.py` — Constructs prompts, manages Gemini client and multi-turn chat sessions, parses structured responses. No file I/O — session data is passed in/out as arguments; `output.py` handles `.session.json` persistence.
- `video.py` — Wraps yt-dlp and ffmpeg as subprocesses. Provides functions for: caption download, stream URL retrieval, frame extraction. All subprocess calls use `subprocess.run` with list args — never `shell=True`, never string interpolation into commands.
- `output.py` — Creates output directories, sanitizes folder names, writes files. Handles the skip/force logic.
- `config.py` — Reads API keys from env vars or `~/.config/vidi/config.toml`. Runs first-time setup prompt when no key is found.

**Dependency direction:** `cli.py` imports from all other modules. `gemini.py`, `video.py`, `output.py`, and `config.py` do not import from each other (except `output.py` may be used by any layer for file writing).

## Commands

| Command | Gemini | yt-dlp | ffmpeg | Output |
|---|---|---|---|---|
| `vidi summarize <url>` | yes | no | no | `summary.md` |
| `vidi ask <url> "question"` | yes | no | no | stdout + `.session.json` |
| `vidi ask --new <url> "question"` | yes | no | no | reset session, ask fresh |
| `vidi timestamps <url>` | yes | no | no | `timestamps.json` |
| `vidi transcript <url>` | no* | yes | no | `transcript.md` |
| `vidi frames <url>` | yes** | no | yes | `frames/*.jpg` |
| `vidi analyze <url>` | yes | yes | yes | all of the above |
| `vidi config show` | no | no | no | stdout (masked key) |
| `vidi config set <key> <value>` | no | no | no | writes config.toml |
| `vidi config path` | no | no | no | stdout |

\* Gemini transcription as fallback if yt-dlp captions unavailable.
\** Requires timestamps — calls Gemini to generate them if `timestamps.json` doesn't already exist.

### Command: `analyze`

Orchestrates all individual commands against a single URL. Each step is an independent Gemini call (not one combined request). Steps run sequentially:

1. `summarize` → writes `summary.md`
2. `timestamps` → writes `timestamps.json`
3. `transcript` → writes `transcript.md`
4. `frames` → reads `timestamps.json`, writes `frames/*.jpg`

Each step writes its output independently. A failure in one step does not abort the others. At the end, a report shows what succeeded and what failed:

```
✓ summary.md
✓ timestamps.json
✗ transcript.md — no captions available, Gemini transcription failed
✓ frames/ (8 frames)
```

### Command: `ask`

Stateful one-shot Q&A. Each invocation is a separate CLI call, but chat history persists in `.session.json` inside the video's output folder.

**Session lifecycle:**
- First `ask` for a video: uploads/references video to Gemini, sends question, creates `.session.json`
- Subsequent `ask`s: loads chat history from `.session.json`, sends question with full context
- `--new` flag: deletes existing `.session.json`, starts fresh session
- Stale Gemini cache (server-side expiration): transparently re-uploads video and replays chat history

**Output:** Answer printed to stdout. Chat history saved to `.session.json`. No separate Q&A log file.

## Output Structure

All output is written to a `vidi/` folder in the current working directory.

```
vidi/
  Video Title - Creator [video_id]/
    summary.md
    timestamps.json
    transcript.md
    frames/
      3m15s.jpg
      8m42s.jpg
    .session.json
```

### Folder naming

Format: `{sanitized_title} - {sanitized_creator} [{video_id}]`

- Title and creator: strip/replace filesystem-unsafe characters (`/ \ : * ? " < > |`), collapse whitespace, truncate to ~80 characters
- Video ID in brackets ensures uniqueness even if two videos produce the same sanitized prefix
- Video ID is extracted from the YouTube URL (the `v` parameter or shortlink path)

### File formats

**`summary.md`:**
```markdown
# {Video Title}
**Creator:** {Channel Name}
**Duration:** {HH:MM:SS}
**URL:** {original URL}

## Overview
Two to three sentences on what this video is about.

## Key Points
- Point one with context
- Point two with context
- Point three with context

## Conclusions
What the video concludes or recommends.
```

**`timestamps.json`:**
```json
[
  {
    "time": "3:15",
    "seconds": 195,
    "label": "introduces the architecture diagram",
    "type": "visual",
    "frame": "3m15s.jpg"
  }
]
```

`type` values: `visual` (slide, diagram, demo), `topic` (new subject), `key_point` (important statement).

**`transcript.md`:**
```markdown
[0:00] Hey everyone, welcome back...
[0:15] Today we're going to look at...
```

Sourced from yt-dlp captions (preferred) or Gemini transcription (fallback).

**`frames/*.jpg`:**

One frame per timestamp. Filename format: `{M}m{SS}s.jpg` (e.g., `3m15s.jpg`). Extracted at the exact timestamp Gemini identifies. Future improvement: grab ~5 candidates within ±1 second window and select the sharpest using ffmpeg scene detection / blur metrics.

**`.session.json`:**

Internal file storing Gemini chat history for the `ask` command. Not intended for direct human consumption.

## Configuration

### API key lookup order

1. `GEMINI_API_KEY` environment variable (highest priority — for CI, scripting, power users)
2. `~/.config/vidi/config.toml`
3. First-run interactive prompt (writes to config.toml)

### First-run setup

When any command is run with no API key found:

```
No Gemini API key found.

1. Go to https://aistudio.google.com/apikey
2. Create an API key
3. Paste it below

Gemini API key: ********

✓ Key saved to ~/.config/vidi/config.toml
```

### Config file

`~/.config/vidi/config.toml`:

```toml
[api]
gemini_key = "..."
# youtube_key = ""  # optional — for metadata enrichment
```

### Config commands

- `vidi config show` — prints current config with key masked
- `vidi config set gemini_key "value"` — updates a config value
- `vidi config path` — prints the config file path

### Optional: YOUTUBE_API_KEY

Documented but never prompted. If set (env var or config.toml), used for metadata enrichment (video title, channel name, duration). Without it, vidi extracts what it can from yt-dlp output or Gemini's response.

## Dependency Detection

Commands that require yt-dlp or ffmpeg check for their presence on PATH before running.

If missing:

```
✗ yt-dlp is not installed.

Install it:
  pip:    pip install yt-dlp
  brew:   brew install yt-dlp
  docs:   https://github.com/yt-dlp/yt-dlp#installation
```

OS detection (platform module) tailors the install instructions.

Gemini-only commands (`summarize`, `ask`, `timestamps`) never check for external deps and work with only a Gemini API key.

yt-dlp can be installed via pip (offer to do it since we're in Python-land). ffmpeg requires system installation — print instructions only, never auto-install.

## Behavioral Rules

### Skip / force

All commands that produce output files skip if the output already exists. `--force` flag overwrites.

`analyze` checks each sub-command's output independently — if `summary.md` exists but `timestamps.json` doesn't, it skips summarize and runs timestamps.

### Security

All subprocess calls (yt-dlp, ffmpeg) use `subprocess.run` with list arguments. Never `shell=True`. Never string interpolation into command strings. URL input is passed as a single argument element, never interpolated into a shell command.

### Error handling

- Individual commands: fail with clear error message and non-zero exit code
- `analyze`: continue on failure, report at end, exit non-zero if any step failed
- API key invalid: print error with instructions to update (`vidi config set gemini_key "..."`)
- Network errors: print error, suggest retry
- Video unavailable (private, age-restricted, deleted): print Gemini's error or yt-dlp's error

## Stack

- **Python 3.11+** — stdlib `tomllib` for config parsing
- **typer** — CLI framework
- **google-generativeai** — Gemini API SDK
- **uv** — project and dependency management
- **Distribution:** `pipx install vidi` or `uv tool install vidi`
- **Dev dependencies:** pytest, semgrep

## Testing

- Unit tests for each module (config parsing, path sanitization, command construction, response parsing)
- Integration tests for CLI commands (mock Gemini responses, mock subprocess calls)
- Security: semgrep scans (`--config auto`) on all code, manual review for subprocess injection vectors
- Review/fix cycles until all issues are resolved

## Quality Process

- Tests written alongside implementation
- `semgrep --config auto` run on security-sensitive code (subprocess calls, input handling, config file I/O)
- Review/fix cycles: iterate until clean. Non-issues are explicitly noted as not issues.
- `progress.txt` maintained in project root, updated as implementation progresses
