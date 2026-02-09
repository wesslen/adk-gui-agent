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

    EVALSET_NAMES = ["basic", "simple", "complex"]

    @pytest.mark.parametrize("name", EVALSET_NAMES)
    def test_load_evalset(self, evalset_dir: Path, name: str):
        """Test loading each eval set file."""
        evalset_path = evalset_dir / f"{name}.evalset.json"

        assert evalset_path.exists(), f"EvalSet not found: {evalset_path}"

        with open(evalset_path) as f:
            evalset = json.load(f)

        assert "eval_set_id" in evalset
        assert "eval_cases" in evalset
        assert len(evalset["eval_cases"]) > 0

    @pytest.mark.parametrize("name", EVALSET_NAMES)
    def test_evalset_structure(self, load_evalset, name: str):
        """Test that each eval set has required ADK structure."""
        evalset = load_evalset(name)

        assert "evaluation_config" in evalset

        for case in evalset["eval_cases"]:
            # Required fields per ADK format
            assert "eval_case_id" in case, f"Missing eval_case_id in {name}"
            assert "conversation" in case, f"Missing conversation in {case.get('eval_case_id')}"
            assert len(case["conversation"]) > 0
            assert case["conversation"][0]["role"] == "user"

            # Every case must define expected_tool_calls and criteria
            assert "expected_tool_calls" in case, (
                f"Missing expected_tool_calls in {case['eval_case_id']}"
            )
            assert "criteria" in case, (
                f"Missing criteria in {case['eval_case_id']}"
            )

    @pytest.mark.parametrize("name", EVALSET_NAMES)
    def test_evalset_ids_unique(self, load_evalset, name: str):
        """Test that eval case IDs are unique within each eval set."""
        evalset = load_evalset(name)
        case_ids = [c["eval_case_id"] for c in evalset["eval_cases"]]
        assert len(case_ids) == len(set(case_ids)), f"Duplicate case IDs in {name}: {case_ids}"

    @pytest.mark.parametrize("name", EVALSET_NAMES)
    def test_evalset_tool_calls_valid(self, load_evalset, name: str):
        """Test that all expected_tool_calls reference known Playwright MCP tools."""
        known_tools = {
            "browser_navigate", "browser_go_back", "browser_go_forward",
            "browser_snapshot", "browser_take_screenshot",
            "browser_click", "browser_type", "browser_hover",
            "browser_select_option", "browser_press_key", "browser_wait_for",
        }

        evalset = load_evalset(name)
        for case in evalset["eval_cases"]:
            for tc in case["expected_tool_calls"]:
                assert tc["tool_name"] in known_tools, (
                    f"Unknown tool '{tc['tool_name']}' in {case['eval_case_id']} ({name})"
                )


# =============================================================================
# Simple Form EvalSet Tests
# =============================================================================


@pytest.mark.evalset
class TestSimpleFormEvalCases:
    """Validate the simple contact form eval set (happy paths + failure modes)."""

    def test_case_count(self, load_evalset):
        """Simple evalset should have 8 cases: 2 happy + 6 failure modes."""
        evalset = load_evalset("simple")
        assert len(evalset["eval_cases"]) == 8

    def test_happy_paths_exist(self, load_evalset):
        """Both happy path cases must exist."""
        evalset = load_evalset("simple")
        case_ids = [c["eval_case_id"] for c in evalset["eval_cases"]]
        assert "simple_happy_complete" in case_ids
        assert "simple_happy_required_only" in case_ids

    def test_failure_modes_exist(self, load_evalset):
        """All 6 failure mode cases must exist."""
        evalset = load_evalset("simple")
        case_ids = [c["eval_case_id"] for c in evalset["eval_cases"]]
        expected_failures = [
            "simple_fail_snapshot_before_interact",
            "simple_fail_stale_ref_after_select",
            "simple_fail_dropdown_must_use_select",
            "simple_fail_required_field_coverage",
            "simple_fail_no_premature_submit",
            "simple_fail_field_data_mapping",
        ]
        for fid in expected_failures:
            assert fid in case_ids, f"Missing failure mode case: {fid}"

    def test_happy_complete_has_all_fields(self, load_evalset):
        """Happy complete case should expect all 6 fields filled."""
        evalset = load_evalset("simple")
        case = next(c for c in evalset["eval_cases"] if c["eval_case_id"] == "simple_happy_complete")
        assert case["criteria"]["min_fields_filled"] == 6
        assert "browser_take_screenshot" in case["criteria"]["must_include_tools"]

    def test_happy_required_only_skips_phone(self, load_evalset):
        """Happy required-only case should expect 5 fields (no phone)."""
        evalset = load_evalset("simple")
        case = next(
            c for c in evalset["eval_cases"] if c["eval_case_id"] == "simple_happy_required_only"
        )
        assert case["criteria"]["min_fields_filled"] == 5

    def test_dropdown_case_requires_select_option(self, load_evalset):
        """Dropdown failure mode must include browser_select_option in must_include_tools."""
        evalset = load_evalset("simple")
        case = next(
            c for c in evalset["eval_cases"]
            if c["eval_case_id"] == "simple_fail_dropdown_must_use_select"
        )
        assert "browser_select_option" in case["criteria"]["must_include_tools"]
        assert "browser_type" in case["criteria"]["must_not_use_for_select"]

    def test_no_submit_case_has_guard(self, load_evalset):
        """Premature submit failure mode must define must_not_include_actions."""
        evalset = load_evalset("simple")
        case = next(
            c for c in evalset["eval_cases"]
            if c["eval_case_id"] == "simple_fail_no_premature_submit"
        )
        assert "must_not_include_actions" in case["criteria"]

    def test_snapshot_before_interact_is_in_order(self, load_evalset):
        """Snapshot-before-interact must use IN_ORDER to enforce sequence."""
        evalset = load_evalset("simple")
        case = next(
            c for c in evalset["eval_cases"]
            if c["eval_case_id"] == "simple_fail_snapshot_before_interact"
        )
        assert case["criteria"]["tool_trajectory_match"] == "IN_ORDER"
        tool_names = [tc["tool_name"] for tc in case["expected_tool_calls"]]
        snap_idx = tool_names.index("browser_snapshot")
        type_idx = tool_names.index("browser_type")
        assert snap_idx < type_idx, "Snapshot must precede first browser_type"


# =============================================================================
# Complex Form EvalSet Tests
# =============================================================================


@pytest.mark.evalset
class TestComplexFormEvalCases:
    """Validate the complex onboarding form eval set (happy paths + failure modes)."""

    def test_case_count(self, load_evalset):
        """Complex evalset should have 10 cases: 2 happy + 8 failure modes."""
        evalset = load_evalset("complex")
        assert len(evalset["eval_cases"]) == 10

    def test_happy_paths_exist(self, load_evalset):
        """Both happy path cases must exist."""
        evalset = load_evalset("complex")
        case_ids = [c["eval_case_id"] for c in evalset["eval_cases"]]
        assert "complex_happy_full_onboarding" in case_ids
        assert "complex_happy_remote_with_equipment" in case_ids

    def test_failure_modes_exist(self, load_evalset):
        """All 8 failure mode cases must exist."""
        evalset = load_evalset("complex")
        case_ids = [c["eval_case_id"] for c in evalset["eval_cases"]]
        expected_failures = [
            "complex_fail_step_navigation",
            "complex_fail_radio_must_use_click",
            "complex_fail_conditional_field_blindness",
            "complex_fail_checkbox_must_use_click",
            "complex_fail_date_format",
            "complex_fail_cross_step_stale_refs",
            "complex_fail_validation_gate",
            "complex_fail_select_value_not_label",
        ]
        for fid in expected_failures:
            assert fid in case_ids, f"Missing failure mode case: {fid}"

    def test_full_onboarding_spans_all_steps(self, load_evalset):
        """Happy full onboarding must include tool calls across all 3 steps."""
        evalset = load_evalset("complex")
        case = next(
            c for c in evalset["eval_cases"]
            if c["eval_case_id"] == "complex_happy_full_onboarding"
        )
        tool_names = [tc["tool_name"] for tc in case["expected_tool_calls"]]

        # Must have multiple snapshots (at least one per step transition)
        snapshot_count = tool_names.count("browser_snapshot")
        assert snapshot_count >= 3, f"Expected >=3 snapshots for 3 steps, got {snapshot_count}"

        # Must have click calls (Next buttons + radio buttons + checkboxes)
        click_count = tool_names.count("browser_click")
        assert click_count >= 5, f"Expected >=5 clicks (Next + radios + checkboxes), got {click_count}"

        assert case["criteria"]["min_fields_filled"] >= 20

    def test_remote_happy_path_has_conditional_flag(self, load_evalset):
        """Remote worker happy path must assert conditional_fields_filled."""
        evalset = load_evalset("complex")
        case = next(
            c for c in evalset["eval_cases"]
            if c["eval_case_id"] == "complex_happy_remote_with_equipment"
        )
        assert case["criteria"].get("conditional_fields_filled") is True

    def test_step_navigation_enforces_click_before_step2(self, load_evalset):
        """Step navigation failure mode must have browser_click before Step 2 select_option."""
        evalset = load_evalset("complex")
        case = next(
            c for c in evalset["eval_cases"]
            if c["eval_case_id"] == "complex_fail_step_navigation"
        )
        tool_names = [tc["tool_name"] for tc in case["expected_tool_calls"]]
        # Find last browser_click (the Next button) and first browser_select_option after it
        last_click_idx = len(tool_names) - 1 - tool_names[::-1].index("browser_click")
        last_select_idx = len(tool_names) - 1 - tool_names[::-1].index("browser_select_option")
        assert last_click_idx < last_select_idx, "Next click must precede Step 2 select"

    def test_radio_case_forbids_type(self, load_evalset):
        """Radio button failure mode must forbid browser_type for radios."""
        evalset = load_evalset("complex")
        case = next(
            c for c in evalset["eval_cases"]
            if c["eval_case_id"] == "complex_fail_radio_must_use_click"
        )
        assert "browser_type" in case["criteria"]["must_not_use_for_radio"]

    def test_date_format_uses_iso(self, load_evalset):
        """Date format failure mode must expect YYYY-MM-DD strings in browser_type args."""
        evalset = load_evalset("complex")
        case = next(
            c for c in evalset["eval_cases"]
            if c["eval_case_id"] == "complex_fail_date_format"
        )
        date_types = [
            tc for tc in case["expected_tool_calls"]
            if tc["tool_name"] == "browser_type" and "arguments" in tc
            and tc["arguments"].get("text", "")[:4].isdigit()
        ]
        import re
        iso_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        for tc in date_types:
            assert iso_pattern.match(tc["arguments"]["text"]), (
                f"Expected ISO date, got: {tc['arguments']['text']}"
            )

    def test_cross_step_refs_requires_resnapshot(self, load_evalset):
        """Cross-step stale refs must have snapshot between click(Next) and next interaction."""
        evalset = load_evalset("complex")
        case = next(
            c for c in evalset["eval_cases"]
            if c["eval_case_id"] == "complex_fail_cross_step_stale_refs"
        )
        tool_names = [tc["tool_name"] for tc in case["expected_tool_calls"]]
        # After the last browser_click, the very next call should be browser_snapshot
        click_indices = [i for i, t in enumerate(tool_names) if t == "browser_click"]
        assert len(click_indices) > 0
        last_click = click_indices[-1]
        assert tool_names[last_click + 1] == "browser_snapshot", (
            "browser_snapshot must immediately follow the Next button click"
        )

    def test_timeout_is_adequate(self, load_evalset):
        """Complex form has 3 steps — timeout should be >= 300s."""
        evalset = load_evalset("complex")
        assert evalset["evaluation_config"]["timeout_seconds"] >= 300


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
