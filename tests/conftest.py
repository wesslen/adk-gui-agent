"""Pytest fixtures for GUI Agent tests.

This module provides fixtures for:
- Configuration setup
- Mock server management
- ADK evaluation helpers
- Agent instance creation
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generator

import pytest

if TYPE_CHECKING:
    from gui_agent_v1.config import Settings


# =============================================================================
# Configuration Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def test_env() -> dict[str, str]:
    """Provide test environment variables.

    Uses API key if available, otherwise falls back to Vertex AI config.
    """
    env = {
        "MODEL_NAME": "gemini-2.5-flash",
        "PLAYWRIGHT_MCP_URL": "http://localhost:3000/sse",
        "BROWSER_HEADLESS": "true",
        "ENABLE_TRACING": "false",  # Disable tracing in tests for speed
        "MAX_AGENT_STEPS": "10",
        "MOCK_SERVER_HOST": "localhost",
        "MOCK_SERVER_PORT": "8080",
    }

    # Check for API key first
    if api_key := os.environ.get("GOOGLE_API_KEY"):
        env["GOOGLE_API_KEY"] = api_key
    else:
        # Fall back to Vertex AI
        env["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"
        env["GOOGLE_CLOUD_PROJECT"] = os.environ.get("GOOGLE_CLOUD_PROJECT", "test-project")
        env["GOOGLE_CLOUD_LOCATION"] = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

    return env


@pytest.fixture
def settings(test_env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> "Settings":
    """Provide configured Settings instance.

    Uses monkeypatch to set environment variables for the test.
    """
    for key, value in test_env.items():
        monkeypatch.setenv(key, value)

    # Clear the cached settings to pick up test config
    from gui_agent_v1.config import get_settings

    get_settings.cache_clear()

    return get_settings()


# =============================================================================
# Mock Server Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def mock_server_url() -> str:
    """Return the mock server URL."""
    return "http://localhost:8080"


@pytest.fixture(scope="session")
def mock_server_process() -> Generator[subprocess.Popen | None, None, None]:
    """Start the mock server for the test session.

    This fixture attempts to start the mock server. If it's already running
    (e.g., via docker-compose), it will skip starting a new process.
    """
    import socket

    def is_port_open(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(("localhost", port)) == 0

    if is_port_open(8080):
        # Server already running
        yield None
        return

    # Start the mock server
    process = subprocess.Popen(
        ["uvicorn", "mock_sites.server:app", "--host", "0.0.0.0", "--port", "8080"],
        cwd=Path(__file__).parent.parent,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server to start
    max_retries = 30
    for _ in range(max_retries):
        if is_port_open(8080):
            break
        time.sleep(0.5)
    else:
        process.kill()
        raise RuntimeError("Mock server failed to start")

    yield process

    # Cleanup
    process.terminate()
    process.wait(timeout=5)


# =============================================================================
# ADK Evaluation Fixtures
# =============================================================================


@pytest.fixture
def evalset_dir() -> Path:
    """Return the path to evaluation sets (co-located with agent source)."""
    return Path(__file__).parent.parent / "gui_agent_v1" / "evals"


@pytest.fixture
def load_evalset(evalset_dir: Path):
    """Factory fixture to load evaluation sets."""

    def _load(name: str) -> dict[str, Any]:
        evalset_path = evalset_dir / f"{name}.evalset.json"
        if not evalset_path.exists():
            raise FileNotFoundError(f"EvalSet not found: {evalset_path}")
        return json.loads(evalset_path.read_text())

    return _load


@pytest.fixture
def form_filling_data() -> dict[str, str]:
    """Provide standard form data for testing."""
    return {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "phone": "555-123-4567",
        "subject": "general",
        "message": "This is a test message from the GUI agent.",
    }


@pytest.fixture
def complex_form_data() -> dict[str, str]:
    """Provide data for the complex employee onboarding form."""
    return {
        "first_name": "Jane",
        "middle_name": "Marie",
        "last_name": "Smith",
        "email": "jane.smith@company.com",
        "phone": "555-987-6543",
        "date_of_birth": "1990-05-15",
        "ssn_last4": "1234",
        "street_address": "123 Main Street",
        "city": "San Francisco",
        "state": "CA",
        "zip_code": "94102",
        "department": "engineering",
        "job_title": "Senior Software Engineer",
        "start_date": "2024-02-01",
        "manager": "sarah.johnson",
        "employment_type": "full-time",
        "work_location": "hybrid",
        "emergency_contact_name": "Bob Smith",
        "emergency_contact_phone": "555-111-2222",
        "emergency_contact_relationship": "spouse",
        "digital_signature": "Jane Marie Smith",
    }


# =============================================================================
# Agent Fixtures
# =============================================================================


@pytest.fixture
def agent_factory(settings: "Settings"):
    """Factory fixture to create configured agents."""
    from gui_agent_v1.agent import create_form_filling_agent

    def _create(model: str | None = None):
        settings.configure_environment()
        return create_form_filling_agent(model=model)

    return _create


# =============================================================================
# Async Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# Test Markers
# =============================================================================


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks tests requiring external services")
    config.addinivalue_line("markers", "evalset: marks tests using ADK evaluation format")
    config.addinivalue_line("markers", "docker: marks tests that validate Docker configuration")
    config.addinivalue_line("markers", "platform: marks tests for platform compatibility (ARM64, OS-specific)")
    config.addinivalue_line("markers", "headed: marks tests for headed mode functionality")
