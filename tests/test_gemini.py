import json
from unittest.mock import patch, MagicMock

import pytest

from vidi.gemini import (
    MODEL_NAME,
    build_summary_prompt,
    build_timestamps_prompt,
    build_transcript_prompt,
    build_video_content,
    create_client,
    format_summary_md,
    format_transcript_md,
    generate_text_content,
    generate_video_content,
    parse_summary_response,
    parse_timestamps_response,
    parse_transcript_response,
)


class TestPrompts:
    def test_summary_prompt_no_url(self):
        prompt = build_summary_prompt()
        assert "http" not in prompt
        assert "TITLE:" in prompt
        assert "CREATOR:" in prompt

    def test_timestamps_prompt_no_url(self):
        prompt = build_timestamps_prompt()
        assert "http" not in prompt
        assert "JSON" in prompt or "json" in prompt

    def test_transcript_prompt_no_url(self):
        prompt = build_transcript_prompt()
        assert "http" not in prompt
        assert "transcript" in prompt.lower()


class TestBuildVideoContent:
    def test_builds_content_with_file_data_and_text(self):
        from google.genai import types
        content = build_video_content("https://youtube.com/watch?v=abc", "Summarize this")
        assert len(content.parts) == 2
        assert content.parts[0].file_data.file_uri == "https://youtube.com/watch?v=abc"
        assert content.parts[1].text == "Summarize this"

    def test_returns_content_type(self):
        from google.genai import types
        content = build_video_content("https://youtube.com/watch?v=xyz", "Analyze")
        assert isinstance(content, types.Content)


class TestGenerateVideoContent:
    def test_calls_generate_content_with_video(self):
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = MagicMock(text="result text")
        result = generate_video_content(mock_client, "https://youtube.com/watch?v=abc", "Prompt")
        assert result == "result text"
        mock_client.models.generate_content.assert_called_once()
        call_kwargs = mock_client.models.generate_content.call_args
        assert call_kwargs.kwargs["model"] == MODEL_NAME

    def test_returns_response_text(self):
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = MagicMock(text="video analysis")
        result = generate_video_content(mock_client, "https://youtube.com/watch?v=abc", "Summarize")
        assert result == "video analysis"


class TestGenerateTextContent:
    def test_calls_generate_content_with_text(self):
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = MagicMock(text="text result")
        result = generate_text_content(mock_client, "Hello")
        assert result == "text result"
        mock_client.models.generate_content.assert_called_once()
        call_kwargs = mock_client.models.generate_content.call_args
        assert call_kwargs.kwargs["model"] == MODEL_NAME
        assert call_kwargs.kwargs["contents"] == "Hello"


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


class TestParseSummaryResponse:
    def test_parses_all_fields(self):
        response_text = """TITLE: My Test Video
CREATOR: Test Channel
DURATION: 5:30

OVERVIEW:
This video covers testing. It is thorough.

KEY POINTS:
- First key point
- Second key point

CONCLUSIONS:
The video wraps up neatly."""
        result = parse_summary_response(response_text)
        assert result["title"] == "My Test Video"
        assert result["creator"] == "Test Channel"
        assert result["duration"] == "5:30"
        assert "testing" in result["overview"]
        assert len(result["key_points"]) == 2
        assert result["key_points"][0] == "First key point"
        assert "wraps up" in result["conclusions"]

    def test_returns_empty_strings_for_missing_fields(self):
        result = parse_summary_response("TITLE: Only Title")
        assert result["title"] == "Only Title"
        assert result["creator"] == ""
        assert result["key_points"] == []

    def test_accumulates_multiline_overview(self):
        response_text = """OVERVIEW:
Line one of overview.
Line two of overview."""
        result = parse_summary_response(response_text)
        assert "Line one" in result["overview"]
        assert "Line two" in result["overview"]


class TestCreateClient:
    @patch("vidi.gemini.genai.Client")
    def test_creates_client_with_key(self, mock_client_class):
        mock_client_instance = MagicMock()
        mock_client_class.return_value = mock_client_instance
        client = create_client("test-key")
        mock_client_class.assert_called_once_with(api_key="test-key")
        assert client is mock_client_instance
