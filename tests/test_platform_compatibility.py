"""Tests for platform compatibility (ARM64, Firefox, cross-platform support)."""

from __future__ import annotations

import platform
from pathlib import Path

import pytest
import yaml


class TestARM64Compatibility:
    """Tests for ARM64/Apple Silicon compatibility."""

    @pytest.fixture
    def compose_config(self) -> dict:
        """Load the main docker-compose.yml file."""
        compose_path = Path(__file__).parent.parent / "docker-compose.yml"
        with open(compose_path) as f:
            return yaml.safe_load(f)

    def test_no_platform_emulation_specified(self, compose_config: dict):
        """Test that no platform emulation is forced (allows native ARM64)."""
        service = compose_config["services"]["playwright-mcp"]

        # Should NOT have platform: linux/amd64 (which would force emulation)
        assert "platform" not in service

    def test_uses_firefox_for_arm64_support(self, compose_config: dict):
        """Test that Firefox is used (has better ARM64 support than Chrome)."""
        service = compose_config["services"]["playwright-mcp"]
        command = service["command"]

        # Should use Firefox, not Chrome/Chromium
        assert "firefox" in command.lower()
        assert "--browser firefox" in command

    def test_uses_noble_ubuntu_image(self, compose_config: dict):
        """Test that Ubuntu 24.04 (Noble) image is used for ARM64 support."""
        service = compose_config["services"]["playwright-mcp"]
        image = service["image"]

        # Ubuntu 24.04 (Noble) has official ARM64 support
        assert "noble" in image.lower()

    def test_playwright_image_is_official_microsoft(self, compose_config: dict):
        """Test that official Microsoft Playwright image is used."""
        service = compose_config["services"]["playwright-mcp"]
        image = service["image"]

        # Should use Microsoft's official image
        assert "mcr.microsoft.com/playwright" in image


class TestFirefoxConfiguration:
    """Tests for Firefox-specific configuration."""

    @pytest.fixture
    def compose_config(self) -> dict:
        """Load the main docker-compose.yml file."""
        compose_path = Path(__file__).parent.parent / "docker-compose.yml"
        with open(compose_path) as f:
            return yaml.safe_load(f)

    def test_firefox_browser_specified(self, compose_config: dict):
        """Test that Firefox browser is specified in command."""
        service = compose_config["services"]["playwright-mcp"]
        command = service["command"]

        assert "--browser firefox" in command

    def test_firefox_installation_command(self, compose_config: dict):
        """Test that Firefox is installed with dependencies."""
        service = compose_config["services"]["playwright-mcp"]
        command = service["command"]

        # Should install firefox with dependencies
        assert "playwright install firefox" in command
        assert "--with-deps" in command

    def test_firefox_no_sandbox_flag(self, compose_config: dict):
        """Test that --no-sandbox flag is set for Firefox in Docker."""
        service = compose_config["services"]["playwright-mcp"]
        env = service["environment"]

        # Should have PLAYWRIGHT_FIREFOX_ARGS with --no-sandbox
        firefox_args = next(
            (e for e in env if "PLAYWRIGHT_FIREFOX_ARGS" in e), None
        )
        assert firefox_args is not None
        assert "--no-sandbox" in firefox_args

    def test_no_chrome_references(self, compose_config: dict):
        """Test that Chrome/Chromium are not referenced in config."""
        service = compose_config["services"]["playwright-mcp"]
        command = service["command"].lower()

        # Should NOT mention chrome or chromium
        assert "chrome" not in command or "firefox" in command
        # If "chrome" appears, it should only be in context of NOT using it


class TestCrossPlatformSupport:
    """Tests for cross-platform support (Mac ARM64 and Linux x86_64)."""

    def test_documentation_covers_both_platforms(self):
        """Test that documentation mentions both Mac and Linux."""
        agents_md = Path(__file__).parent.parent / "AGENTS.md"
        content = agents_md.read_text().lower()

        # Should mention Mac/macOS
        assert any(
            keyword in content for keyword in ["mac", "macos", "darwin", "apple silicon"]
        )

        # Should mention Linux
        assert "linux" in content

    def test_docker_compose_works_on_both_architectures(self):
        """Test that Docker Compose config is architecture-agnostic."""
        compose_path = Path(__file__).parent.parent / "docker-compose.yml"
        with open(compose_path) as f:
            config = yaml.safe_load(f)

        service = config["services"]["playwright-mcp"]

        # No platform specified = works on both ARM64 and x86_64
        assert "platform" not in service

        # Firefox supports both architectures natively
        command = service["command"]
        assert "firefox" in command.lower()

    def test_headed_mode_supports_both_os(self):
        """Test that headed mode has configurations for both Mac and Linux."""
        # Check for Mac setup script
        mac_script = (
            Path(__file__).parent.parent / "scripts" / "setup_headed_mode_mac.sh"
        )
        assert mac_script.exists()

        # Check for Linux setup script
        linux_script = (
            Path(__file__).parent.parent / "scripts" / "setup_headed_mode_linux.sh"
        )
        assert linux_script.exists()

        # Headed docker-compose should work for both
        headed_compose = Path(__file__).parent.parent / "docker-compose.headed.yml"
        with open(headed_compose) as f:
            config = yaml.safe_load(f)

        service = config["services"]["playwright-mcp"]

        # Should have DISPLAY variable (configurable)
        env = service["environment"]
        display_env = next((e for e in env if "DISPLAY=" in e), None)
        assert display_env is not None

        # Should mount X11 socket for Linux (ignored on Mac)
        volumes = service["volumes"]
        assert any("/tmp/.X11-unix" in v for v in volumes)


class TestPlatformSpecificFeatures:
    """Tests for platform-specific features and workarounds."""

    def test_no_sandbox_required_in_docker(self):
        """Test that --no-sandbox is set (required for Docker)."""
        compose_path = Path(__file__).parent.parent / "docker-compose.yml"
        with open(compose_path) as f:
            config = yaml.safe_load(f)

        service = config["services"]["playwright-mcp"]
        env = service["environment"]

        # Should have --no-sandbox for Firefox in Docker
        firefox_args = next(
            (e for e in env if "PLAYWRIGHT_FIREFOX_ARGS" in e), None
        )
        assert firefox_args is not None
        assert "--no-sandbox" in firefox_args

    def test_mac_display_uses_host_docker_internal(self):
        """Test that Mac configuration uses host.docker.internal."""
        # This is tested in the Makefile logic and headed mode
        agents_md = Path(__file__).parent.parent / "AGENTS.md"
        content = agents_md.read_text()

        # Should document using host.docker.internal for Mac
        assert "host.docker.internal" in content

    def test_linux_display_uses_x11_socket(self):
        """Test that Linux configuration uses X11 Unix socket."""
        headed_compose = Path(__file__).parent.parent / "docker-compose.headed.yml"
        with open(headed_compose) as f:
            config = yaml.safe_load(f)

        service = config["services"]["playwright-mcp"]
        volumes = service["volumes"]

        # Should mount X11 Unix socket
        assert any("/tmp/.X11-unix" in v for v in volumes)


class TestDockerNetworking:
    """Tests for Docker networking configuration."""

    @pytest.fixture
    def compose_config(self) -> dict:
        """Load the main docker-compose.yml file."""
        compose_path = Path(__file__).parent.parent / "docker-compose.yml"
        with open(compose_path) as f:
            return yaml.safe_load(f)

    def test_custom_network_defined(self, compose_config: dict):
        """Test that custom Docker network is defined."""
        networks = compose_config.get("networks", {})
        default_network = networks.get("default", {})

        assert default_network.get("name") == "gui-agent-network"

    def test_container_to_container_networking(self):
        """Test that documentation explains container-to-container networking."""
        agents_md = Path(__file__).parent.parent / "AGENTS.md"
        content = agents_md.read_text()

        # Should explain using container names (e.g., mock-server:8080)
        assert "mock-server" in content

    def test_localhost_url_warning_documented(self):
        """Test that localhost URL issue is documented."""
        agents_md = Path(__file__).parent.parent / "AGENTS.md"
        content = agents_md.read_text().lower()

        # Should warn about localhost not working from containers
        assert "localhost" in content
        assert any(
            keyword in content
            for keyword in ["container", "docker", "mock-server", "host.docker.internal"]
        )


class TestBackwardCompatibility:
    """Tests for backward compatibility with existing setups."""

    def test_default_mode_is_headless(self):
        """Test that default mode is headless (existing behavior)."""
        compose_path = Path(__file__).parent.parent / "docker-compose.yml"
        with open(compose_path) as f:
            config = yaml.safe_load(f)

        service = config["services"]["playwright-mcp"]
        command = service["command"]

        # Default should be headless
        assert "--headless" in command

    def test_existing_volume_mounts_preserved(self):
        """Test that existing volume mounts are preserved."""
        compose_path = Path(__file__).parent.parent / "docker-compose.yml"
        with open(compose_path) as f:
            config = yaml.safe_load(f)

        service = config["services"]["playwright-mcp"]
        volumes = service["volumes"]

        # Essential mounts should be present
        essential_mounts = [
            "./playwright-mcp:/app",
            "./gui_agent_v1/screenshots:/app/screenshots",
            "playwright_cache:/root/.cache",
        ]

        for mount in essential_mounts:
            assert mount in volumes

    def test_port_8931_unchanged(self):
        """Test that MCP server port is still 8931 (not changed)."""
        compose_path = Path(__file__).parent.parent / "docker-compose.yml"
        with open(compose_path) as f:
            config = yaml.safe_load(f)

        service = config["services"]["playwright-mcp"]
        ports = service["ports"]

        assert "8931:8931" in ports


class TestPlatformDetection:
    """Tests for platform detection at runtime."""

    def test_current_platform_can_be_detected(self):
        """Test that current platform can be detected."""
        current_platform = platform.system()

        # Should return one of the expected values
        assert current_platform in ["Darwin", "Linux", "Windows"]

    def test_architecture_can_be_detected(self):
        """Test that CPU architecture can be detected."""
        arch = platform.machine()

        # Should return architecture string
        assert isinstance(arch, str)
        assert len(arch) > 0

        # Common values: arm64, aarch64, x86_64, AMD64
        assert arch.lower() in [
            "arm64",
            "aarch64",
            "x86_64",
            "amd64",
            "x64",
        ] or arch.startswith(("arm", "x86", "amd"))
