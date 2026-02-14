"""Tests for Docker Compose configuration files."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


class TestDockerComposeBase:
    """Tests for the base docker-compose.yml file."""

    @pytest.fixture
    def compose_config(self) -> dict:
        """Load the main docker-compose.yml file."""
        compose_path = Path(__file__).parent.parent / "docker-compose.yml"
        with open(compose_path) as f:
            return yaml.safe_load(f)

    def test_playwright_mcp_service_exists(self, compose_config: dict):
        """Test that playwright-mcp service is defined."""
        assert "playwright-mcp" in compose_config["services"]

    def test_playwright_mcp_uses_firefox(self, compose_config: dict):
        """Test that playwright-mcp is configured to use Firefox."""
        service = compose_config["services"]["playwright-mcp"]
        command = service["command"]

        # Should install firefox
        assert "firefox" in command.lower()
        assert "--browser firefox" in command

    def test_playwright_mcp_uses_headless_by_default(self, compose_config: dict):
        """Test that headless mode is the default."""
        service = compose_config["services"]["playwright-mcp"]
        command = service["command"]

        # Should have --headless flag
        assert "--headless" in command

    def test_playwright_mcp_has_no_platform_specification(self, compose_config: dict):
        """Test that no platform is specified (allows native ARM64)."""
        service = compose_config["services"]["playwright-mcp"]

        # Should NOT have platform specified (native architecture)
        assert "platform" not in service

    def test_playwright_mcp_port_is_8931(self, compose_config: dict):
        """Test that MCP server uses port 8931."""
        service = compose_config["services"]["playwright-mcp"]
        ports = service["ports"]

        assert "8931:8931" in ports

    def test_screenshot_volume_mount(self, compose_config: dict):
        """Test that screenshots directory is mounted."""
        service = compose_config["services"]["playwright-mcp"]
        volumes = service["volumes"]

        # Should mount screenshots directory
        screenshot_mount = "./gui_agent_v1/screenshots:/app/screenshots"
        assert screenshot_mount in volumes

    def test_playwright_firefox_args_env(self, compose_config: dict):
        """Test that Firefox args are set via environment."""
        service = compose_config["services"]["playwright-mcp"]
        env = service["environment"]

        # Should have Firefox args with --no-sandbox
        firefox_args = next(
            (e for e in env if e.startswith("PLAYWRIGHT_FIREFOX_ARGS=")), None
        )
        assert firefox_args is not None
        assert "--no-sandbox" in firefox_args

    def test_output_dir_configuration(self, compose_config: dict):
        """Test that output directory is configured."""
        service = compose_config["services"]["playwright-mcp"]

        # Environment variable
        env = service["environment"]
        assert "PLAYWRIGHT_MCP_OUTPUT_DIR=/app" in env

        # Command line flag
        command = service["command"]
        assert "--output-dir /app" in command

    def test_working_directory_is_app(self, compose_config: dict):
        """Test that working directory is /app."""
        service = compose_config["services"]["playwright-mcp"]
        assert service["working_dir"] == "/app"

    def test_phoenix_service_exists(self, compose_config: dict):
        """Test that Phoenix observability service is defined."""
        assert "phoenix" in compose_config["services"]

    def test_mock_server_has_testing_profile(self, compose_config: dict):
        """Test that mock server is in testing profile."""
        service = compose_config["services"]["mock-server"]
        profiles = service.get("profiles", [])

        assert "testing" in profiles

    def test_network_name(self, compose_config: dict):
        """Test that custom network is defined."""
        networks = compose_config.get("networks", {})
        default_network = networks.get("default", {})

        assert default_network.get("name") == "gui-agent-network"


class TestDockerComposeHeaded:
    """Tests for the docker-compose.headed.yml override file."""

    @pytest.fixture
    def headed_config(self) -> dict:
        """Load the docker-compose.headed.yml file."""
        headed_path = Path(__file__).parent.parent / "docker-compose.headed.yml"
        with open(headed_path) as f:
            return yaml.safe_load(f)

    def test_headed_removes_headless_flag(self, headed_config: dict):
        """Test that headed mode does NOT have --headless flag."""
        service = headed_config["services"]["playwright-mcp"]
        command = service["command"]

        # Should NOT have --headless
        assert "--headless" not in command

    def test_headed_uses_display_variable(self, headed_config: dict):
        """Test that DISPLAY environment variable is configurable."""
        service = headed_config["services"]["playwright-mcp"]
        env = service["environment"]

        # Should use HEADED_DISPLAY variable with fallback
        display_env = next((e for e in env if e.startswith("DISPLAY=")), None)
        assert display_env is not None
        assert "${HEADED_DISPLAY" in display_env

    def test_headed_has_x11_volume_mount(self, headed_config: dict):
        """Test that X11 Unix socket is mounted for Linux."""
        service = headed_config["services"]["playwright-mcp"]
        volumes = service["volumes"]

        # Should mount X11 socket (used on Linux, ignored on Mac)
        x11_mount = "/tmp/.X11-unix:/tmp/.X11-unix:rw"
        assert x11_mount in volumes

    def test_headed_still_has_screenshots_mount(self, headed_config: dict):
        """Test that screenshot volume is still mounted in headed mode."""
        service = headed_config["services"]["playwright-mcp"]
        volumes = service["volumes"]

        screenshot_mount = "./gui_agent_v1/screenshots:/app/screenshots"
        assert screenshot_mount in volumes

    def test_headed_preserves_firefox_configuration(self, headed_config: dict):
        """Test that Firefox configuration is preserved in headed mode."""
        service = headed_config["services"]["playwright-mcp"]

        # Environment
        env = service["environment"]
        firefox_args = next(
            (e for e in env if e.startswith("PLAYWRIGHT_FIREFOX_ARGS=")), None
        )
        assert firefox_args is not None

        # Command
        command = service["command"]
        assert "--browser firefox" in command


class TestDockerComposeIntegration:
    """Integration tests for Docker Compose configurations."""

    def test_compose_files_are_valid_yaml(self):
        """Test that all Docker Compose files are valid YAML."""
        project_root = Path(__file__).parent.parent
        compose_files = [
            "docker-compose.yml",
            "docker-compose.headed.yml",
        ]

        for filename in compose_files:
            compose_path = project_root / filename
            assert compose_path.exists(), f"Missing: {filename}"

            with open(compose_path) as f:
                try:
                    config = yaml.safe_load(f)
                    assert isinstance(config, dict)
                except yaml.YAMLError as e:
                    pytest.fail(f"Invalid YAML in {filename}: {e}")

    def test_headed_overrides_are_compatible(self):
        """Test that headed overrides work with base config."""
        project_root = Path(__file__).parent.parent

        # Load both configs
        with open(project_root / "docker-compose.yml") as f:
            base = yaml.safe_load(f)

        with open(project_root / "docker-compose.headed.yml") as f:
            headed = yaml.safe_load(f)

        # Both should define playwright-mcp
        assert "playwright-mcp" in base["services"]
        assert "playwright-mcp" in headed["services"]

        # Headed should override specific keys
        headed_service = headed["services"]["playwright-mcp"]
        assert "environment" in headed_service
        assert "command" in headed_service


class TestFirefoxConfiguration:
    """Tests for Firefox-specific configuration."""

    @pytest.fixture
    def compose_config(self) -> dict:
        """Load the main docker-compose.yml file."""
        compose_path = Path(__file__).parent.parent / "docker-compose.yml"
        with open(compose_path) as f:
            return yaml.safe_load(f)

    def test_uses_firefox_not_chrome(self, compose_config: dict):
        """Test that configuration uses Firefox, not Chrome."""
        service = compose_config["services"]["playwright-mcp"]
        command = service["command"]

        # Should install and use firefox
        assert "firefox" in command.lower()
        assert "chrome" not in command.lower()
        assert "chromium" not in command.lower()

    def test_firefox_no_sandbox_flag(self, compose_config: dict):
        """Test that --no-sandbox is set for Firefox in Docker."""
        service = compose_config["services"]["playwright-mcp"]
        env = service["environment"]

        firefox_args = next(
            (e for e in env if "PLAYWRIGHT_FIREFOX_ARGS" in e), None
        )
        assert firefox_args is not None
        assert "--no-sandbox" in firefox_args

    def test_playwright_image_supports_arm64(self, compose_config: dict):
        """Test that Playwright image used supports ARM64."""
        service = compose_config["services"]["playwright-mcp"]
        image = service["image"]

        # Using official Microsoft Playwright image
        assert "mcr.microsoft.com/playwright" in image

        # Should use noble (Ubuntu 24.04) which supports ARM64
        assert "noble" in image

    def test_no_gpu_flags_for_firefox(self, compose_config: dict):
        """Test that GPU-related flags are not used (Firefox handles differently)."""
        service = compose_config["services"]["playwright-mcp"]
        command = service["command"]

        # Should NOT have GPU disable flags (those were for Chrome)
        assert "--disable-gpu" not in command
        assert "--disable-dev-shm-usage" not in command
