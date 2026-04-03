import json
from pathlib import Path

import pytest

from vidi.output import (
    extract_video_id,
    find_existing_output_dir,
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
        assert sanitize_filename('Hello / World: "Test"') == "Hello World Test"

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


class TestFindExistingOutputDir:
    def test_finds_existing_dir(self, tmp_path):
        video_dir = tmp_path / "vidi" / "Some Video - Creator [abc123]"
        video_dir.mkdir(parents=True)
        result = find_existing_output_dir("abc123", base_dir=tmp_path)
        assert result == video_dir

    def test_returns_none_when_not_found(self, tmp_path):
        (tmp_path / "vidi").mkdir()
        result = find_existing_output_dir("nonexistent", base_dir=tmp_path)
        assert result is None

    def test_returns_none_when_no_vidi_dir(self, tmp_path):
        result = find_existing_output_dir("abc123", base_dir=tmp_path)
        assert result is None


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
