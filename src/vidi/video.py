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
