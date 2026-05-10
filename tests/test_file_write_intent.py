"""Tests for file write intent parsing."""

from __future__ import annotations

from app.services.host_executor_intent import parse_file_write_intent


class TestFileWriteIntent:
    """Test natural language file write intent parsing."""

    def test_write_pattern(self) -> None:
        """Test 'write filename with content' pattern."""
        result = parse_file_write_intent("write test.txt with Hello World")
        assert result is not None
        assert result["filename"] == "test.txt"
        assert result["content"] == "Hello World"
        assert result["directory"] is None

    def test_create_file_pattern(self) -> None:
        """Test 'Create a file called filename with content content' pattern."""
        result = parse_file_write_intent("Create a file called data.json with content {'test': true}")
        assert result is not None
        assert result["filename"] == "data.json"
        assert result["content"] == "{'test': true}"
        assert result["directory"] is None

    def test_write_to_pattern(self) -> None:
        """Test 'write quoted content to filename' pattern."""
        result = parse_file_write_intent("write 'hello there' to notes.txt")
        assert result is not None
        assert result["filename"] == "notes.txt"
        assert result["content"] == "hello there"
        assert result["directory"] is None

    def test_write_to_file_with_content_pattern(self) -> None:
        """Test 'write to filename with content' pattern."""
        result = parse_file_write_intent("write to notes.txt with hello there")
        assert result is not None
        assert result["filename"] == "notes.txt"
        assert result["content"] == "hello there"
        assert result["directory"] is None

    def test_non_file_intent(self) -> None:
        """Test non-file intent returns None."""
        result = parse_file_write_intent("What's the weather like?")
        assert result is None

    def test_empty_string(self) -> None:
        """Test empty string returns None."""
        result = parse_file_write_intent("")
        assert result is None

    def test_with_directory(self) -> None:
        """Test with directory specified."""
        result = parse_file_write_intent(
            "Create a file called test.txt with content hello in /Users/test"
        )
        assert result is not None
        assert result["filename"] == "test.txt"
        assert result["content"] == "hello"
        assert result["directory"] == "/Users/test"
