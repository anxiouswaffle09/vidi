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
