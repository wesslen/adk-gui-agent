"""Tests for screenshot functionality and path handling."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from unittest.mock import Mock

import pytest

if TYPE_CHECKING:
    from gui_agent_v1.config import Settings


class TestScreenshotCallback:
    """Tests for the screenshot callback function."""

    def test_screenshot_callback_adds_timestamp(self, settings: "Settings"):
        """Test that screenshot filenames get timestamped."""
        from gui_agent_v1.agent import _screenshot_callback

        # Mock tool and context
        tool = Mock()
        tool.name = "browser_take_screenshot"
        tool_context = Mock()

        args = {"filename": "test.png"}
        _screenshot_callback(tool, args, tool_context)

        # Should have timestamp prefix in format: YYYYMMDD_HHMMSS_
        filename = args["filename"]
        assert re.match(r"/app/screenshots/\d{8}_\d{6}_test\.png", filename)

    def test_screenshot_callback_uses_absolute_path(self, settings: "Settings"):
        """Test that screenshots use absolute paths for Docker."""
        from gui_agent_v1.agent import _screenshot_callback

        tool = Mock()
        tool.name = "browser_take_screenshot"
        tool_context = Mock()

        args = {"filename": "my_screenshot.png"}
        _screenshot_callback(tool, args, tool_context)

        # Should start with /app/screenshots/ (absolute path in container)
        assert args["filename"].startswith("/app/screenshots/")

    def test_screenshot_callback_sanitizes_filename(self, settings: "Settings"):
        """Test that unsafe characters are removed from filenames."""
        from gui_agent_v1.agent import _screenshot_callback

        tool = Mock()
        tool.name = "browser_take_screenshot"
        tool_context = Mock()

        # Filename with unsafe characters (no directory path)
        args = {"filename": "my test file@#$.png"}
        _screenshot_callback(tool, args, tool_context)

        # Should sanitize: spaces, special chars -> underscores
        filename = args["filename"].split("/")[-1]  # Get just the filename
        # The callback strips directory prefix first, then sanitizes
        # So "my test file@#$.png" -> "my_test_file_.png"
        assert re.match(r"\d{8}_\d{6}_my_test_file_.png", filename)

    def test_screenshot_callback_adds_extension(self, settings: "Settings"):
        """Test that .png extension is added if missing."""
        from gui_agent_v1.agent import _screenshot_callback

        tool = Mock()
        tool.name = "browser_take_screenshot"
        tool_context = Mock()

        args = {"filename": "screenshot_no_ext"}
        _screenshot_callback(tool, args, tool_context)

        # Should add .png extension
        assert args["filename"].endswith(".png")

    def test_screenshot_callback_default_filename(self, settings: "Settings"):
        """Test that default filename is used when not provided."""
        from gui_agent_v1.agent import _screenshot_callback

        tool = Mock()
        tool.name = "browser_take_screenshot"
        tool_context = Mock()

        args = {}  # No filename provided
        _screenshot_callback(tool, args, tool_context)

        # Should create default: /app/screenshots/YYYYMMDD_HHMMSS_screenshot.png
        assert "filename" in args
        assert re.match(
            r"/app/screenshots/\d{8}_\d{6}_screenshot\.png", args["filename"]
        )

    def test_screenshot_callback_ignores_other_tools(self, settings: "Settings"):
        """Test that callback only modifies browser_take_screenshot calls."""
        from gui_agent_v1.agent import _screenshot_callback

        tool = Mock()
        tool.name = "browser_navigate"  # Different tool
        tool_context = Mock()

        args = {"filename": "test.png"}
        original_args = args.copy()

        result = _screenshot_callback(tool, args, tool_context)

        # Should return None and not modify args
        assert result is None
        assert args == original_args

    def test_screenshot_directory_configuration(self, monkeypatch: pytest.MonkeyPatch):
        """Test that screenshot directory can be configured."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        monkeypatch.setenv("SCREENSHOT_DIR", "custom_screenshots")

        from gui_agent_v1.config import get_settings

        get_settings.cache_clear()
        settings = get_settings()

        assert settings.screenshot_dir == "custom_screenshots"

    def test_filename_sanitization_edge_cases(self, settings: "Settings"):
        """Test filename sanitization with edge cases."""
        from gui_agent_v1.agent import _sanitize_filename

        # Multiple consecutive special chars -> single underscore
        assert _sanitize_filename("test___file") == "test_file"

        # Leading/trailing underscores removed
        assert _sanitize_filename("_test_") == "test"

        # Dots preserved (for extensions)
        assert _sanitize_filename("test.file.png") == "test.file.png"

        # Hyphens preserved
        assert _sanitize_filename("test-file-name") == "test-file-name"


class TestScreenshotPathHandling:
    """Tests for screenshot path handling in Docker."""

    def test_screenshot_path_matches_volume_mount(self, settings: "Settings"):
        """Test that screenshot paths align with Docker volume mount."""
        from gui_agent_v1.agent import _screenshot_callback

        tool = Mock()
        tool.name = "browser_take_screenshot"
        tool_context = Mock()

        args = {"filename": "test.png"}
        _screenshot_callback(tool, args, tool_context)

        # Path should be /app/screenshots/... to match volume mount:
        # ./gui_agent_v1/screenshots:/app/screenshots
        path = args["filename"]
        assert path.startswith("/app/screenshots/")

        # Should not have nested directories
        path_parts = path.split("/")
        assert len(path_parts) == 4  # ['', 'app', 'screenshots', 'filename.png']

    def test_screenshot_path_strips_directory_prefix(self, settings: "Settings"):
        """Test that LLM-added directory prefixes are stripped."""
        from gui_agent_v1.agent import _screenshot_callback

        tool = Mock()
        tool.name = "browser_take_screenshot"
        tool_context = Mock()

        # LLM might add a path prefix
        args = {"filename": "some/nested/path/screenshot.png"}
        _screenshot_callback(tool, args, tool_context)

        # Should only keep the base filename
        filename_part = args["filename"].split("/")[-1]
        assert re.match(r"\d{8}_\d{6}_screenshot\.png", filename_part)

    def test_timestamp_format_is_sortable(self, settings: "Settings"):
        """Test that timestamp format allows chronological sorting."""
        from gui_agent_v1.agent import _screenshot_callback

        tool = Mock()
        tool.name = "browser_take_screenshot"
        tool_context = Mock()

        # Create multiple screenshots
        filenames = []
        for _ in range(3):
            args = {"filename": "test.png"}
            _screenshot_callback(tool, args, tool_context)
            filenames.append(args["filename"])

        # Timestamps should be sortable strings (YYYYMMDD_HHMMSS)
        sorted_filenames = sorted(filenames)
        assert filenames == sorted_filenames  # Already in chronological order


class TestScreenshotSettings:
    """Tests for screenshot-related settings."""

    def test_default_screenshot_dir(self, monkeypatch: pytest.MonkeyPatch):
        """Test default screenshot directory setting."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

        from gui_agent_v1.config import get_settings

        get_settings.cache_clear()
        settings = get_settings()

        assert settings.screenshot_dir == "screenshots"

    def test_custom_screenshot_dir_from_env(self, monkeypatch: pytest.MonkeyPatch):
        """Test that screenshot dir can be set via environment variable."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        monkeypatch.setenv("SCREENSHOT_DIR", "my_custom_dir")

        from gui_agent_v1.config import get_settings

        get_settings.cache_clear()
        settings = get_settings()

        assert settings.screenshot_dir == "my_custom_dir"
