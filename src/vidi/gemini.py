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
