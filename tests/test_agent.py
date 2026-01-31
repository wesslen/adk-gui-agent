"""Integration tests for the GUI agent.

These tests verify the agent can perform form-filling tasks using the
ADK evaluation format adapted for pytest.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from gui_agent.config import Settings


# =============================================================================
# Unit Tests (No external services required)
# =============================================================================


class TestAgentCreation:
    """Tests for agent creation and configuration."""

    def test_create_agent(self, settings: "Settings"):
        """Test that the agent can be created with valid settings."""
        from gui_agent.agent import create_form_filling_agent

        settings.configure_environment()

        # Note: This doesn't connect to MCP server, just creates the agent config
        agent = create_form_filling_agent(toolset=None)

        assert agent.name == "form_filling_agent"
        assert "form" in agent.instruction.lower()

    def test_agent_has_correct_model(self, settings: "Settings"):
        """Test that the agent uses the configured model."""
        from gui_agent.agent import create_form_filling_agent

        settings.configure_environment()
        agent = create_form_filling_agent(model="gemini-2.0-flash", toolset=None)

        # Model is set on the agent
        assert agent.model == "gemini-2.0-flash"


class TestSystemPrompts:
    """Tests for system prompts."""

    def test_form_filling_prompt_content(self):
        """Test that the form filling prompt contains expected guidance."""
        from gui_agent.prompts import FORM_FILLING_SYSTEM_PROMPT

        prompt = FORM_FILLING_SYSTEM_PROMPT.lower()

        # Should mention key capabilities
        assert "form" in prompt
        assert "fill" in prompt
        assert "screenshot" in prompt
        assert "verification" in prompt

    def test_prompt_includes_safety_guidelines(self):
        """Test that prompts include safety considerations."""
        from gui_agent.prompts import FORM_FILLING_SYSTEM_PROMPT

        prompt = FORM_FILLING_SYSTEM_PROMPT.lower()

        # Should have safety guidelines
        assert "password" in prompt or "payment" in prompt
        assert "submit" in prompt


# =============================================================================
# EvalSet-Based Tests
# =============================================================================


class TestEvalSetLoader:
    """Tests for loading and validating eval sets."""

    def test_load_basic_evalset(self, evalset_dir: Path):
        """Test loading the basic form filling eval set."""
        evalset_path = evalset_dir / "form_filling" / "basic.evalset.json"

        assert evalset_path.exists(), f"EvalSet not found: {evalset_path}"

        with open(evalset_path) as f:
            evalset = json.load(f)

        assert "eval_set_id" in evalset
        assert "eval_cases" in evalset
        assert len(evalset["eval_cases"]) > 0

    def test_evalset_structure(self, load_evalset):
        """Test that eval set has required structure."""
        evalset = load_evalset("form_filling", "basic")

        for case in evalset["eval_cases"]:
            assert "eval_case_id" in case
            assert "conversation" in case
            assert len(case["conversation"]) > 0
            assert case["conversation"][0]["role"] == "user"


@pytest.mark.evalset
class TestFormFillingEvalCases:
    """Eval-based tests for form filling scenarios.

    These tests validate the expected behavior defined in evalsets.
    They are marked as evalset tests and can be run separately.
    """

    def test_simple_form_complete_case_exists(self, load_evalset):
        """Verify the simple form complete test case exists and is valid."""
        evalset = load_evalset("form_filling", "basic")

        case_ids = [c["eval_case_id"] for c in evalset["eval_cases"]]
        assert "simple_form_complete" in case_ids

        case = next(c for c in evalset["eval_cases"] if c["eval_case_id"] == "simple_form_complete")

        # Verify expected tool calls
        assert "expected_tool_calls" in case
        tool_names = [tc["tool_name"] for tc in case["expected_tool_calls"]]
        assert "browser_navigate" in tool_names
        assert "browser_type" in tool_names

    def test_screenshot_verification_case(self, load_evalset):
        """Verify screenshot verification test case."""
        evalset = load_evalset("form_filling", "basic")

        case = next(
            (c for c in evalset["eval_cases"] if c["eval_case_id"] == "simple_form_screenshot_verify"),
            None,
        )

        assert case is not None
        assert "browser_screenshot" in [tc["tool_name"] for tc in case["expected_tool_calls"]]


# =============================================================================
# Integration Tests (Require external services)
# =============================================================================


@pytest.mark.integration
@pytest.mark.slow
class TestFormFillingIntegration:
    """Integration tests requiring mock server and Playwright MCP.

    These tests are marked as integration tests and require:
    - Mock server running on port 8080
    - Playwright MCP server running on port 3000

    Run with: pytest -m integration
    """

    @pytest.fixture(autouse=True)
    def setup(self, mock_server_process, settings: "Settings"):
        """Ensure mock server is running before tests."""
        self.settings = settings

    @pytest.mark.skip(reason="Requires running Playwright MCP server")
    async def test_navigate_to_simple_form(self):
        """Test navigating to the simple form page."""
        from gui_agent.agent import run_agent_task

        result = await run_agent_task(
            "Navigate to http://localhost:8080/simple and describe what you see"
        )

        assert "contact" in result.lower() or "form" in result.lower()

    @pytest.mark.skip(reason="Requires running Playwright MCP server")
    async def test_fill_simple_form(self, form_filling_data: dict[str, str]):
        """Test filling the simple contact form."""
        from gui_agent.agent import run_agent_task

        task = f"""
        Navigate to http://localhost:8080/simple and fill the contact form with:
        - First Name: {form_filling_data['first_name']}
        - Last Name: {form_filling_data['last_name']}
        - Email: {form_filling_data['email']}
        - Phone: {form_filling_data['phone']}
        - Subject: General Inquiry
        - Message: {form_filling_data['message']}

        Do not submit the form. Take a screenshot when done.
        """

        result = await run_agent_task(task)

        # Verify agent reported filling the form
        assert "filled" in result.lower() or "complete" in result.lower()


# =============================================================================
# Regression Test Helpers
# =============================================================================


def evaluate_tool_trajectory(
    actual_calls: list[dict[str, Any]],
    expected_calls: list[dict[str, Any]],
    match_type: str = "IN_ORDER",
) -> float:
    """Evaluate tool call trajectory against expected calls.

    Args:
        actual_calls: List of actual tool calls made by the agent.
        expected_calls: List of expected tool calls from eval set.
        match_type: One of "EXACT", "IN_ORDER", or "ANY_ORDER".

    Returns:
        Score between 0.0 and 1.0.
    """
    if not expected_calls:
        return 1.0

    if not actual_calls:
        return 0.0

    actual_names = [c.get("tool_name") for c in actual_calls]
    expected_names = [c.get("tool_name") for c in expected_calls]

    if match_type == "EXACT":
        if actual_names == expected_names:
            return 1.0
        return 0.0

    elif match_type == "IN_ORDER":
        # Expected calls should appear in order within actual calls
        expected_idx = 0
        for actual_name in actual_names:
            if expected_idx < len(expected_names) and actual_name == expected_names[expected_idx]:
                expected_idx += 1

        return expected_idx / len(expected_names)

    elif match_type == "ANY_ORDER":
        # All expected calls should appear somewhere in actual calls
        found = sum(1 for name in expected_names if name in actual_names)
        return found / len(expected_names)

    return 0.0


class TestTrajectoryEvaluation:
    """Tests for the trajectory evaluation helper."""

    def test_exact_match(self):
        """Test exact trajectory matching."""
        actual = [{"tool_name": "a"}, {"tool_name": "b"}, {"tool_name": "c"}]
        expected = [{"tool_name": "a"}, {"tool_name": "b"}, {"tool_name": "c"}]

        assert evaluate_tool_trajectory(actual, expected, "EXACT") == 1.0

    def test_exact_match_fails_with_extra(self):
        """Test exact match fails with extra calls."""
        actual = [{"tool_name": "a"}, {"tool_name": "x"}, {"tool_name": "b"}]
        expected = [{"tool_name": "a"}, {"tool_name": "b"}]

        assert evaluate_tool_trajectory(actual, expected, "EXACT") == 0.0

    def test_in_order_match(self):
        """Test in-order matching allows extra calls between."""
        actual = [{"tool_name": "a"}, {"tool_name": "x"}, {"tool_name": "b"}, {"tool_name": "c"}]
        expected = [{"tool_name": "a"}, {"tool_name": "b"}, {"tool_name": "c"}]

        assert evaluate_tool_trajectory(actual, expected, "IN_ORDER") == 1.0

    def test_in_order_partial(self):
        """Test in-order with partial match."""
        actual = [{"tool_name": "a"}, {"tool_name": "b"}]
        expected = [{"tool_name": "a"}, {"tool_name": "b"}, {"tool_name": "c"}]

        score = evaluate_tool_trajectory(actual, expected, "IN_ORDER")
        assert 0.6 <= score <= 0.7  # 2/3

    def test_any_order_match(self):
        """Test any-order matching."""
        actual = [{"tool_name": "c"}, {"tool_name": "a"}, {"tool_name": "b"}]
        expected = [{"tool_name": "a"}, {"tool_name": "b"}, {"tool_name": "c"}]

        assert evaluate_tool_trajectory(actual, expected, "ANY_ORDER") == 1.0
