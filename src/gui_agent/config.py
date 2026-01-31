"""Configuration module with authentication fallback logic.

Authentication Priority:
1. GOOGLE_API_KEY - If set, uses Google AI Studio directly
2. Vertex AI - If GOOGLE_API_KEY not set, uses gcloud authentication with:
   - GOOGLE_GENAI_USE_VERTEXAI=TRUE
   - GOOGLE_CLOUD_PROJECT
   - GOOGLE_CLOUD_LOCATION
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # =========================================================================
    # LLM Authentication
    # =========================================================================
    # Option 1: Google AI Studio (direct API key)
    google_api_key: str | None = Field(default=None, alias="GOOGLE_API_KEY")

    # Option 2: Vertex AI (gcloud authentication)
    google_genai_use_vertexai: bool = Field(default=False, alias="GOOGLE_GENAI_USE_VERTEXAI")
    google_cloud_project: str | None = Field(default=None, alias="GOOGLE_CLOUD_PROJECT")
    google_cloud_location: str = Field(default="us-central1", alias="GOOGLE_CLOUD_LOCATION")

    # =========================================================================
    # Model Configuration
    # =========================================================================
    model_name: str = Field(default="gemini-2.5-flash", alias="MODEL_NAME")

    # =========================================================================
    # Playwright MCP Server
    # =========================================================================
    playwright_mcp_url: str = Field(
        default="http://localhost:3000/sse",
        alias="PLAYWRIGHT_MCP_URL",
    )
    browser_headless: bool = Field(default=True, alias="BROWSER_HEADLESS")
    browser_timeout: int = Field(default=30, alias="BROWSER_TIMEOUT")

    # =========================================================================
    # Observability - Arize Phoenix
    # =========================================================================
    phoenix_host: str = Field(default="localhost", alias="PHOENIX_HOST")
    phoenix_port: int = Field(default=6006, alias="PHOENIX_PORT")
    phoenix_collector_endpoint: str = Field(
        default="http://localhost:6006/v1/traces",
        alias="PHOENIX_COLLECTOR_ENDPOINT",
    )
    enable_tracing: bool = Field(default=True, alias="ENABLE_TRACING")

    # =========================================================================
    # Agent Configuration
    # =========================================================================
    max_agent_steps: int = Field(default=20, alias="MAX_AGENT_STEPS")

    # =========================================================================
    # Mock Server
    # =========================================================================
    mock_server_host: str = Field(default="localhost", alias="MOCK_SERVER_HOST")
    mock_server_port: int = Field(default=8080, alias="MOCK_SERVER_PORT")

    @model_validator(mode="after")
    def validate_auth_config(self) -> "Settings":
        """Ensure valid authentication configuration."""
        if not self.google_api_key and not self.google_genai_use_vertexai:
            # Default to Vertex AI if no API key provided
            self.google_genai_use_vertexai = True

        if self.google_genai_use_vertexai and not self.google_cloud_project:
            raise ValueError(
                "GOOGLE_CLOUD_PROJECT must be set when using Vertex AI authentication. "
                "Either set GOOGLE_API_KEY or configure Vertex AI credentials."
            )

        return self

    @property
    def auth_mode(self) -> Literal["api_key", "vertex_ai"]:
        """Return the active authentication mode."""
        if self.google_api_key:
            return "api_key"
        return "vertex_ai"

    @property
    def mock_server_url(self) -> str:
        """Return the full mock server URL."""
        return f"http://{self.mock_server_host}:{self.mock_server_port}"

    @property
    def phoenix_ui_url(self) -> str:
        """Return the Phoenix UI URL."""
        return f"http://{self.phoenix_host}:{self.phoenix_port}"

    def configure_environment(self) -> None:
        """Set environment variables for ADK/genai library.

        This method sets the environment variables that the google-genai
        library expects for authentication.
        """
        if self.google_api_key:
            os.environ["GOOGLE_API_KEY"] = self.google_api_key
            # Ensure Vertex AI mode is disabled when using API key
            os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "FALSE"
        else:
            os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"
            os.environ["GOOGLE_CLOUD_PROJECT"] = self.google_cloud_project or ""
            os.environ["GOOGLE_CLOUD_LOCATION"] = self.google_cloud_location

    def __str__(self) -> str:
        """Return a safe string representation (no secrets)."""
        return (
            f"Settings(\n"
            f"  auth_mode={self.auth_mode},\n"
            f"  model={self.model_name},\n"
            f"  vertex_ai_project={self.google_cloud_project},\n"
            f"  vertex_ai_location={self.google_cloud_location},\n"
            f"  playwright_mcp_url={self.playwright_mcp_url},\n"
            f"  browser_headless={self.browser_headless},\n"
            f"  phoenix_endpoint={self.phoenix_collector_endpoint},\n"
            f"  tracing_enabled={self.enable_tracing}\n"
            f")"
        )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Use this function to access settings throughout the application
    to ensure consistent configuration.

    Returns:
        Settings: The application settings.

    Raises:
        ValueError: If required configuration is missing.
    """
    return Settings()
