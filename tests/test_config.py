"""Tests for the configuration module."""

from __future__ import annotations

import os

import pytest


class TestSettings:
    """Tests for Settings configuration."""

    def test_api_key_auth_mode(self, monkeypatch: pytest.MonkeyPatch):
        """Test that API key is preferred when set."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key")
        monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")

        from gui_agent.config import get_settings

        get_settings.cache_clear()
        settings = get_settings()

        assert settings.auth_mode == "api_key"
        assert settings.google_api_key == "test-api-key"

    def test_vertex_ai_auth_mode(self, monkeypatch: pytest.MonkeyPatch):
        """Test Vertex AI auth mode when API key not set."""
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
        monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")

        from gui_agent.config import get_settings

        get_settings.cache_clear()
        settings = get_settings()

        assert settings.auth_mode == "vertex_ai"
        assert settings.google_cloud_project == "test-project"
        assert settings.google_cloud_location == "us-central1"

    def test_vertex_ai_requires_project(self, monkeypatch: pytest.MonkeyPatch):
        """Test that Vertex AI mode requires a project ID."""
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
        # Disable .env file loading for this test
        monkeypatch.setenv("PYDANTIC_SETTINGS_ENV_FILE", "")

        from gui_agent.config import Settings, get_settings

        get_settings.cache_clear()

        with pytest.raises(ValueError, match="GOOGLE_CLOUD_PROJECT must be set"):
            Settings(_env_file=None)

    def test_default_values(self, monkeypatch: pytest.MonkeyPatch):
        """Test default configuration values."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

        from gui_agent.config import get_settings

        get_settings.cache_clear()
        settings = get_settings()

        assert settings.model_name == "gemini-2.5-flash"
        assert settings.playwright_mcp_url == "http://localhost:8931/sse"
        assert settings.browser_headless is True
        assert settings.phoenix_port == 6006
        assert settings.max_agent_steps == 20

    def test_configure_environment_api_key(self, monkeypatch: pytest.MonkeyPatch):
        """Test environment configuration for API key mode."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key")

        from gui_agent.config import get_settings

        get_settings.cache_clear()
        settings = get_settings()
        settings.configure_environment()

        assert os.environ.get("GOOGLE_API_KEY") == "test-api-key"
        assert os.environ.get("GOOGLE_GENAI_USE_VERTEXAI") == "FALSE"

    def test_configure_environment_vertex_ai(self, monkeypatch: pytest.MonkeyPatch):
        """Test environment configuration for Vertex AI mode."""
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "my-project")
        monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "europe-west1")

        from gui_agent.config import get_settings

        get_settings.cache_clear()
        settings = get_settings()
        settings.configure_environment()

        assert os.environ.get("GOOGLE_GENAI_USE_VERTEXAI") == "TRUE"
        assert os.environ.get("GOOGLE_CLOUD_PROJECT") == "my-project"
        assert os.environ.get("GOOGLE_CLOUD_LOCATION") == "europe-west1"

    def test_mock_server_url(self, monkeypatch: pytest.MonkeyPatch):
        """Test mock server URL property."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        monkeypatch.setenv("MOCK_SERVER_HOST", "testhost")
        monkeypatch.setenv("MOCK_SERVER_PORT", "9999")

        from gui_agent.config import get_settings

        get_settings.cache_clear()
        settings = get_settings()

        assert settings.mock_server_url == "http://testhost:9999"

    def test_phoenix_ui_url(self, monkeypatch: pytest.MonkeyPatch):
        """Test Phoenix UI URL property."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        monkeypatch.setenv("PHOENIX_HOST", "phoenix.local")
        monkeypatch.setenv("PHOENIX_PORT", "7007")

        from gui_agent.config import get_settings

        get_settings.cache_clear()
        settings = get_settings()

        assert settings.phoenix_ui_url == "http://phoenix.local:7007"
