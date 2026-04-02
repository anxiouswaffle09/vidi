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
