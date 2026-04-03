import json
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
    @patch("vidi.cli.find_existing_output_dir", return_value=None)
    @patch("vidi.cli.file_exists", return_value=False)
    @patch("vidi.cli.get_api_key", return_value="test-key")
    @patch("vidi.cli.create_client")
    @patch("vidi.cli.extract_video_id", return_value="abc123")
    @patch("vidi.cli.build_output_dir")
    @patch("vidi.cli.generate_video_content")
    def test_summarize_calls_gemini(self, mock_gen, mock_dir, mock_id, mock_client, mock_key, mock_exists, mock_find):
        mock_dir.return_value = Path("/tmp/vidi/Test [abc123]")
        mock_gen.side_effect = [
            "TITLE: Test Video\nCREATOR: Test Channel",  # _resolve_output_dir
            """TITLE: Test Video
CREATOR: Test Channel
DURATION: 10:30

OVERVIEW:
This is a test video about testing.

KEY POINTS:
- First point
- Second point

CONCLUSIONS:
Testing is important.""",  # summarize
        ]

        with patch("vidi.cli.write_file"):
            result = runner.invoke(app, ["summarize", "https://youtube.com/watch?v=abc123"])
        assert result.exit_code == 0

    @patch("vidi.cli.find_existing_output_dir", return_value=None)
    @patch("vidi.cli.file_exists", return_value=True)
    @patch("vidi.cli.get_api_key", return_value="test-key")
    @patch("vidi.cli.create_client")
    @patch("vidi.cli.extract_video_id", return_value="abc123")
    @patch("vidi.cli.build_output_dir")
    @patch("vidi.cli.generate_video_content")
    def test_summarize_skips_existing(self, mock_gen, mock_dir, mock_id, mock_client, mock_key, mock_exists, mock_find):
        mock_dir.return_value = Path("/tmp/vidi/Test [abc123]")
        mock_gen.return_value = "TITLE: Test Video\nCREATOR: Test Channel"
        result = runner.invoke(app, ["summarize", "https://youtube.com/watch?v=abc123"])
        assert result.exit_code == 0
        assert "exists" in result.output.lower() or "skip" in result.output.lower()

    @patch("vidi.cli.find_existing_output_dir")
    @patch("vidi.cli.file_exists", return_value=False)
    @patch("vidi.cli.get_api_key", return_value="test-key")
    @patch("vidi.cli.create_client")
    @patch("vidi.cli.extract_video_id", return_value="abc123")
    @patch("vidi.cli.generate_video_content")
    def test_summarize_uses_existing_dir(self, mock_gen, mock_id, mock_client, mock_key, mock_exists, mock_find):
        existing = Path("/tmp/vidi/Cached Video - Chan [abc123]")
        mock_find.return_value = existing
        mock_gen.side_effect = [
            """TITLE: Test Video
CREATOR: Test Channel
DURATION: 10:30

OVERVIEW:
This is a test video about testing.

KEY POINTS:
- First point
- Second point

CONCLUSIONS:
Testing is important.""",
        ]

        with patch("vidi.cli.write_file"):
            result = runner.invoke(app, ["summarize", "https://youtube.com/watch?v=abc123"])
        assert result.exit_code == 0
        # Only one Gemini call (the summarize itself) — no title/creator call
        assert mock_gen.call_count == 1


class TestTimestampsCommand:
    @patch("vidi.cli.find_existing_output_dir", return_value=None)
    @patch("vidi.cli.file_exists", return_value=False)
    @patch("vidi.cli.get_api_key", return_value="test-key")
    @patch("vidi.cli.create_client")
    @patch("vidi.cli.extract_video_id", return_value="abc123")
    @patch("vidi.cli.build_output_dir")
    @patch("vidi.cli.generate_video_content")
    def test_timestamps_writes_json(self, mock_gen, mock_dir, mock_id, mock_client, mock_key, mock_exists, mock_find):
        mock_dir.return_value = Path("/tmp/vidi/Test [abc123]")
        mock_gen.side_effect = [
            "TITLE: Test Video\nCREATOR: Test Channel",  # _resolve_output_dir
            '[{"time": "1:30", "seconds": 90, "label": "intro", "type": "topic"}]',  # timestamps
        ]

        with patch("vidi.cli.write_file"):
            result = runner.invoke(app, ["timestamps", "https://youtube.com/watch?v=abc123"])
        assert result.exit_code == 0


class TestTranscriptCommand:
    @patch("vidi.cli.find_existing_output_dir", return_value=None)
    @patch("vidi.cli.file_exists", return_value=False)
    @patch("vidi.cli.get_api_key", return_value="test-key")
    @patch("vidi.cli.create_client")
    @patch("vidi.cli.extract_video_id", return_value="abc123")
    @patch("vidi.cli.build_output_dir")
    @patch("vidi.cli.check_dependency", return_value=False)
    @patch("vidi.cli.generate_video_content")
    def test_transcript_gemini_fallback(self, mock_gen, mock_dep, mock_dir, mock_id, mock_client, mock_key, mock_exists, mock_find):
        mock_dir.return_value = Path("/tmp/vidi/Test [abc123]")
        mock_gen.side_effect = [
            "TITLE: Test\nCREATOR: Chan",  # _resolve_output_dir
            "[0:00] Hello everyone\n[0:15] Welcome",  # transcript
        ]
        with patch("vidi.cli.write_file"):
            result = runner.invoke(app, ["transcript", "https://youtube.com/watch?v=abc123"])
        assert result.exit_code == 0


class TestFramesCommand:
    @patch("vidi.cli.find_existing_output_dir", return_value=None)
    @patch("vidi.cli.file_exists")
    @patch("vidi.cli.get_api_key", return_value="test-key")
    @patch("vidi.cli.create_client")
    @patch("vidi.cli.extract_video_id", return_value="abc123")
    @patch("vidi.cli.build_output_dir")
    @patch("vidi.cli.check_dependency", return_value=True)
    @patch("vidi.cli.get_stream_url", return_value="https://stream.url/video")
    @patch("vidi.cli.extract_frame", return_value=True)
    @patch("vidi.cli.generate_video_content")
    def test_frames_extracts(self, mock_gen, mock_extract, mock_stream, mock_dep, mock_dir, mock_id, mock_client, mock_key, mock_exists, mock_find):
        mock_dir.return_value = Path("/tmp/vidi/Test [abc123]")
        mock_gen.return_value = "TITLE: Test\nCREATOR: Chan"

        def exists_side_effect(path):
            return "timestamps.json" in str(path)
        mock_exists.side_effect = exists_side_effect

        ts_data = json.dumps([{"time": "1:30", "seconds": 90, "label": "intro", "type": "topic", "frame": "1m30s.jpg"}])
        with patch.object(Path, "read_text", return_value=ts_data):
            result = runner.invoke(app, ["frames", "https://youtube.com/watch?v=abc123", "--force"])
        assert result.exit_code == 0


class TestAnalyzeCommand:
    @patch("vidi.cli.find_existing_output_dir", return_value=None)
    @patch("vidi.cli.check_dependency", return_value=True)
    @patch("vidi.cli.get_api_key", return_value="test-key")
    @patch("vidi.cli.create_client")
    @patch("vidi.cli.extract_video_id", return_value="abc123")
    @patch("vidi.cli.build_output_dir")
    @patch("vidi.cli.generate_video_content")
    def test_analyze_runs_all_steps(self, mock_gen, mock_dir, mock_id, mock_client, mock_key, mock_dep, mock_find):
        mock_dir.return_value = Path("/tmp/vidi/Test [abc123]")
        mock_gen.side_effect = [
            "TITLE: Test\nCREATOR: Chan",  # _resolve_output_dir
            "TITLE: Test\nCREATOR: Chan\nDURATION: 10:00\n\nOVERVIEW:\nA test.\n\nKEY POINTS:\n- Point\n\nCONCLUSIONS:\nDone.",  # summarize
            '[{"time": "1:30", "seconds": 90, "label": "intro", "type": "topic"}]',  # timestamps
            "[0:00] Hello world",  # transcript (Gemini fallback)
        ]

        with patch("vidi.cli.write_file"):
            with patch("vidi.cli.file_exists", return_value=False):
                with patch("vidi.cli.download_captions", return_value=None):
                    with patch("vidi.cli.get_stream_url", return_value="https://stream.url"):
                        with patch("vidi.cli.extract_frame", return_value=True):
                            result = runner.invoke(app, ["analyze", "https://youtube.com/watch?v=abc123"])

        assert result.exit_code == 0
        assert "summary" in result.output.lower()


class TestAskCommand:
    @patch("vidi.cli.find_existing_output_dir", return_value=None)
    @patch("vidi.cli.load_session", return_value=None)
    @patch("vidi.cli.save_session")
    @patch("vidi.cli.get_api_key", return_value="test-key")
    @patch("vidi.cli.create_client")
    @patch("vidi.cli.extract_video_id", return_value="abc123")
    @patch("vidi.cli.build_output_dir")
    @patch("vidi.cli.generate_video_content")
    def test_ask_prints_answer(self, mock_gen, mock_dir, mock_id, mock_client, mock_key, mock_save, mock_load, mock_find):
        mock_dir.return_value = Path("/tmp/vidi/Test [abc123]")
        mock_gen.return_value = "TITLE: Test\nCREATOR: Chan"

        mock_client_instance = MagicMock()
        mock_chat = MagicMock()
        mock_chat.send_message.return_value = MagicMock(text="The video discusses React 19.")
        mock_part = MagicMock()
        mock_part.text = "The video discusses React 19."
        mock_history_msg = MagicMock()
        mock_history_msg.role = "model"
        mock_history_msg.parts = [mock_part]
        mock_chat.history = [mock_history_msg]
        mock_client_instance.chats.create.return_value = mock_chat
        mock_client.return_value = mock_client_instance

        result = runner.invoke(app, ["ask", "https://youtube.com/watch?v=abc123", "What framework?"])
        assert result.exit_code == 0
        assert "React" in result.output
