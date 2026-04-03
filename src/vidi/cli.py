from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import typer

from vidi.config import get_api_key, get_config_path, load_config, save_config, mask_key
from vidi.gemini import (
    MODEL_NAME,
    build_summary_prompt,
    build_timestamps_prompt,
    build_transcript_prompt,
    create_client,
    format_summary_md,
    format_transcript_md,
    generate_text_content,
    generate_video_content,
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


# --- Helper ---

def _resolve_output_dir(url: str, client: object) -> tuple[Path, str]:
    """Get or create the output directory for a video."""
    video_id = extract_video_id(url)
    response_text = generate_video_content(
        client, url,
        "Return ONLY two lines:\nTITLE: the video title\nCREATOR: the channel name"
    )
    title, creator = video_id, "Unknown"
    for line in response_text.strip().split("\n"):
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
    client = create_client(key)
    output_dir, video_id = _resolve_output_dir(url, client)
    summary_path = output_dir / "summary.md"

    if file_exists(summary_path) and not force:
        typer.echo("✓ summary.md already exists (use --force to overwrite)")
        return

    typer.echo("Analyzing video...")
    response_text = generate_video_content(client, url, build_summary_prompt())
    parsed = parse_summary_response(response_text)
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
    typer.echo("✓ summary.md")


@app.command()
def timestamps(
    url: str = typer.Argument(help="YouTube video URL"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing output"),
) -> None:
    """Extract key moments from a YouTube video."""
    key = _require_api_key()
    client = create_client(key)
    output_dir, video_id = _resolve_output_dir(url, client)
    timestamps_path = output_dir / "timestamps.json"

    if file_exists(timestamps_path) and not force:
        typer.echo("✓ timestamps.json already exists (use --force to overwrite)")
        return

    typer.echo("Identifying key moments...")
    response_text = generate_video_content(client, url, build_timestamps_prompt())
    ts_data = parse_timestamps_response(response_text)

    for entry in ts_data:
        entry["frame"] = f"{format_timestamp(entry['seconds'])}.jpg"

    write_file(timestamps_path, json.dumps(ts_data, indent=2) + "\n")
    typer.echo(f"✓ timestamps.json ({len(ts_data)} moments)")


@app.command()
def transcript(
    url: str = typer.Argument(help="YouTube video URL"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing output"),
) -> None:
    """Get video transcript (captions or Gemini fallback)."""
    key = _require_api_key()
    client = create_client(key)
    output_dir, video_id = _resolve_output_dir(url, client)
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
        shutil.rmtree(output_dir / ".tmp_captions", ignore_errors=True)
    else:
        typer.echo(get_install_instructions("yt-dlp"))
        typer.echo("\nUsing Gemini transcription as fallback...")

    # Fallback to Gemini transcription
    if not segments:
        typer.echo("Transcribing with Gemini...")
        response_text = generate_video_content(client, url, build_transcript_prompt())
        segments = parse_transcript_response(response_text)

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

    for dep in ("yt-dlp", "ffmpeg"):
        if not check_dependency(dep):
            typer.echo(get_install_instructions(dep), err=True)
            raise typer.Exit(1)

    client = create_client(key)
    output_dir, video_id = _resolve_output_dir(url, client)
    frames_dir = output_dir / "frames"
    timestamps_path = output_dir / "timestamps.json"

    if not file_exists(timestamps_path):
        typer.echo("Generating timestamps first...")
        response_text = generate_video_content(client, url, build_timestamps_prompt())
        ts_data = parse_timestamps_response(response_text)
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
def analyze(
    url: str = typer.Argument(help="YouTube video URL"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing output"),
) -> None:
    """Run full analysis: summarize, timestamps, transcript, frames."""
    key = _require_api_key()
    client = create_client(key)
    output_dir, video_id = _resolve_output_dir(url, client)

    results = []

    # Step 1: Summarize
    try:
        summary_path = output_dir / "summary.md"
        if file_exists(summary_path) and not force:
            results.append(("summary.md", True, "already exists"))
        else:
            response_text = generate_video_content(client, url, build_summary_prompt())
            parsed = parse_summary_response(response_text)
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
            response_text = generate_video_content(client, url, build_timestamps_prompt())
            ts_data = parse_timestamps_response(response_text)
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
                shutil.rmtree(output_dir / ".tmp_captions", ignore_errors=True)
            if not segments:
                response_text = generate_video_content(client, url, build_transcript_prompt())
                segments = parse_transcript_response(response_text)
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


@app.command()
def ask(
    url: str = typer.Argument(help="YouTube video URL"),
    question: str = typer.Argument(help="Question about the video"),
    new: bool = typer.Option(False, "--new", help="Start a fresh session"),
) -> None:
    """Ask a question about a YouTube video."""
    key = _require_api_key()
    client = create_client(key)
    output_dir, video_id = _resolve_output_dir(url, client)
    session_path = output_dir / ".session.json"

    if new and session_path.exists():
        session_path.unlink()

    session_data = load_session(session_path)

    chat = client.chats.create(model=MODEL_NAME)

    if session_data and session_data.get("history"):
        # Replay history into the chat by sending all previous messages
        for msg in session_data["history"]:
            if msg["role"] == "user":
                chat.send_message(message=msg["parts"][0] if isinstance(msg["parts"], list) else msg["parts"])
    else:
        # New session: send video URL as context in first message
        chat.send_message(message=f"I want to ask questions about this YouTube video: {url}")

    response = chat.send_message(message=question)
    typer.echo(response.text)

    history = []
    for msg in chat.history:
        parts = [p.text for p in msg.parts if hasattr(p, "text") and p.text]
        history.append({"role": msg.role, "parts": parts})

    save_session(session_path, {
        "video_url": url,
        "video_id": video_id,
        "history": history,
    })
