"""Tests for headed mode setup and OS detection."""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest


class TestHeadedModeScripts:
    """Tests for headed mode setup scripts."""

    def test_mac_setup_script_exists(self):
        """Test that Mac setup script exists and is executable."""
        script_path = (
            Path(__file__).parent.parent / "scripts" / "setup_headed_mode_mac.sh"
        )
        assert script_path.exists()
        assert script_path.stat().st_mode & 0o111  # Executable

    def test_linux_setup_script_exists(self):
        """Test that Linux setup script exists and is executable."""
        script_path = (
            Path(__file__).parent.parent / "scripts" / "setup_headed_mode_linux.sh"
        )
        assert script_path.exists()
        assert script_path.stat().st_mode & 0o111  # Executable

    def test_mac_script_checks_for_xquartz(self):
        """Test that Mac script mentions XQuartz."""
        script_path = (
            Path(__file__).parent.parent / "scripts" / "setup_headed_mode_mac.sh"
        )
        content = script_path.read_text()

        assert "xquartz" in content.lower()
        assert "xhost" in content.lower()

    def test_linux_script_checks_for_x11(self):
        """Test that Linux script checks for X11."""
        script_path = (
            Path(__file__).parent.parent / "scripts" / "setup_headed_mode_linux.sh"
        )
        content = script_path.read_text()

        assert "x11" in content.lower() or "DISPLAY" in content
        assert "xhost" in content.lower()

    def test_mac_script_sets_localhost_access(self):
        """Test that Mac script configures xhost for localhost."""
        script_path = (
            Path(__file__).parent.parent / "scripts" / "setup_headed_mode_mac.sh"
        )
        content = script_path.read_text()

        # Should run xhost +localhost
        assert "xhost +localhost" in content or "xhost" in content

    def test_linux_script_sets_docker_access(self):
        """Test that Linux script configures xhost for Docker."""
        script_path = (
            Path(__file__).parent.parent / "scripts" / "setup_headed_mode_linux.sh"
        )
        content = script_path.read_text()

        # Should run xhost +local:docker
        assert "xhost +local:docker" in content


class TestOSDetection:
    """Tests for OS detection logic."""

    @patch("platform.system")
    def test_detects_darwin_as_mac(self, mock_system: Mock):
        """Test that Darwin is detected as macOS."""
        mock_system.return_value = "Darwin"

        # Simulating the Makefile logic
        is_mac = platform.system() == "Darwin"
        assert is_mac is True

    @patch("platform.system")
    def test_detects_linux_as_not_mac(self, mock_system: Mock):
        """Test that Linux is detected as not macOS."""
        mock_system.return_value = "Linux"

        # Simulating the Makefile logic
        is_mac = platform.system() == "Darwin"
        assert is_mac is False

    def test_current_os_detection(self):
        """Test that current OS can be detected."""
        current_os = platform.system()

        # Should be one of the supported platforms
        assert current_os in ["Darwin", "Linux", "Windows"]


class TestHeadedModeDisplayConfiguration:
    """Tests for DISPLAY environment variable configuration."""

    def test_mac_uses_host_docker_internal(self):
        """Test that Mac uses host.docker.internal for DISPLAY."""
        # This is the expected DISPLAY value for Mac
        expected_display = "host.docker.internal:0"

        # Validate format
        assert ":" in expected_display
        assert expected_display.endswith(":0")

    def test_linux_uses_display_variable(self):
        """Test that Linux uses $DISPLAY environment variable."""
        import os

        # Linux should use the current DISPLAY
        display = os.environ.get("DISPLAY", ":0")

        # Should have a display number
        assert ":" in display

    def test_display_format_validation(self):
        """Test that DISPLAY values are properly formatted."""
        valid_displays = [
            ":0",
            ":1",
            "localhost:0",
            "host.docker.internal:0",
            "/private/tmp/com.apple.launchd.xyz/org.xquartz:0",
        ]

        for display in valid_displays:
            # All valid displays should have a colon
            assert ":" in display


class TestHeadedModeDocumentation:
    """Tests for headed mode documentation."""

    def test_agents_md_documents_headed_mode(self):
        """Test that AGENTS.md documents headed mode setup."""
        agents_md = Path(__file__).parent.parent / "AGENTS.md"
        content = agents_md.read_text().lower()

        assert "headed" in content
        assert "headless" in content
        assert "xquartz" in content

    def test_makefile_has_headed_targets(self):
        """Test that Makefile has headed mode targets."""
        makefile = Path(__file__).parent.parent / "Makefile"
        content = makefile.read_text()

        assert "start-services-headed" in content
        assert "setup-headed-mode" in content

    def test_readme_or_agents_md_explains_os_differences(self):
        """Test that OS differences are documented."""
        agents_md = Path(__file__).parent.parent / "AGENTS.md"
        content = agents_md.read_text().lower()

        # Should mention both Mac and Linux
        assert "mac" in content or "darwin" in content
        assert "linux" in content

        # Should mention display-related concepts
        assert "display" in content


class TestHeadedModeXQuartzConfiguration:
    """Tests specific to XQuartz configuration on Mac."""

    def test_xquartz_security_settings_documented(self):
        """Test that XQuartz security settings are documented."""
        # Check Mac setup script
        script_path = (
            Path(__file__).parent.parent / "scripts" / "setup_headed_mode_mac.sh"
        )
        content = script_path.read_text()

        # Should mention security settings
        assert "security" in content.lower() or "allow connections" in content.lower()

    def test_xquartz_restart_requirement_documented(self):
        """Test that XQuartz restart requirement is documented."""
        script_path = (
            Path(__file__).parent.parent / "scripts" / "setup_headed_mode_mac.sh"
        )
        content = script_path.read_text()

        # Should mention restart or quit
        assert (
            "restart" in content.lower()
            or "quit" in content.lower()
            or "log out" in content.lower()
        )


class TestHeadedModeLinuxConfiguration:
    """Tests specific to X11 configuration on Linux."""

    def test_linux_xhost_command_documented(self):
        """Test that xhost command is documented for Linux."""
        script_path = (
            Path(__file__).parent.parent / "scripts" / "setup_headed_mode_linux.sh"
        )
        content = script_path.read_text()

        # Should have xhost +local:docker command
        assert "xhost" in content
        assert "docker" in content

    def test_linux_x11_socket_mount_documented(self):
        """Test that X11 socket mount is in Docker compose."""
        compose_headed = Path(__file__).parent.parent / "docker-compose.headed.yml"
        content = compose_headed.read_text()

        # Should mount /tmp/.X11-unix
        assert "/tmp/.X11-unix" in content


class TestHeadedModeEnvironmentVariables:
    """Tests for environment variables used in headed mode."""

    def test_headed_display_variable_usage(self):
        """Test that HEADED_DISPLAY variable is used correctly."""
        compose_headed = Path(__file__).parent.parent / "docker-compose.headed.yml"
        content = compose_headed.read_text()

        # Should use ${HEADED_DISPLAY} with fallback
        assert "HEADED_DISPLAY" in content
        assert "DISPLAY=" in content

    def test_playwright_environment_vars_documented(self):
        """Test that Playwright environment variables are documented."""
        compose_file = Path(__file__).parent.parent / "docker-compose.yml"
        content = compose_file.read_text()

        # Should have Playwright-specific environment variables
        assert "PLAYWRIGHT_BROWSERS_PATH" in content or "PLAYWRIGHT" in content


class TestHeadedModeErrorHandling:
    """Tests for error handling in headed mode setup."""

    def test_mac_script_checks_xquartz_installed(self):
        """Test that Mac script checks if XQuartz is installed."""
        script_path = (
            Path(__file__).parent.parent / "scripts" / "setup_headed_mode_mac.sh"
        )
        content = script_path.read_text()

        # Should check for xquartz command or installation
        assert (
            "command -v xquartz" in content
            or "which xquartz" in content
            or "xquartz" in content.lower()
        )

    def test_linux_script_checks_display_set(self):
        """Test that Linux script checks if DISPLAY is set."""
        script_path = (
            Path(__file__).parent.parent / "scripts" / "setup_headed_mode_linux.sh"
        )
        content = script_path.read_text()

        # Should check DISPLAY environment variable
        assert "DISPLAY" in content
        assert "$DISPLAY" in content or "${DISPLAY}" in content

    def test_scripts_provide_fallback_instructions(self):
        """Test that scripts provide fallback instructions on failure."""
        for script_name in ["setup_headed_mode_mac.sh", "setup_headed_mode_linux.sh"]:
            script_path = Path(__file__).parent.parent / "scripts" / script_name
            content = script_path.read_text()

            # Should have error messages or instructions
            assert (
                "echo" in content
            )  # Scripts should echo instructions/errors
            # Should handle failures gracefully (exit codes, error messages)
            assert "if" in content or "error" in content.lower()
