"""ADK Agent definition for GUI automation.

This module defines the root_agent that ADK discovers and uses for
form-filling tasks with Playwright MCP tools.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.mcp_tool import McpToolset, SseConnectionParams
from google.genai import types

from gui_agent_v1.config import get_settings
from gui_agent_v1.observability import TracingContext, setup_adk_instrumentation, setup_tracing
from gui_agent_v1.prompts import FORM_FILLING_SYSTEM_PROMPT

if TYPE_CHECKING:
    from google.adk.agents import Agent
    from google.adk.tools import BaseTool, ToolContext

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Screenshot filename callback
# ---------------------------------------------------------------------------

def _sanitize_filename(name: str) -> str:
    """Sanitize a filename to only contain safe characters."""
    # Replace spaces and special chars with underscores
    name = re.sub(r"[^\w\-.]", "_", name)
    # Collapse multiple underscores
    name = re.sub(r"_+", "_", name)
    return name.strip("_")


def _screenshot_callback(
    tool: "BaseTool",
    args: dict[str, Any],
    tool_context: "ToolContext",
) -> dict[str, Any] | None:
    """Intercept browser_take_screenshot calls to add timestamped filenames.

    This ADK before_tool_callback ensures every screenshot gets a unique,
    timestamped filename so repeated task runs never overwrite previous
    screenshots.

    File location strategy:
      - The callback prepends ``screenshots/`` to the filename so the
        Playwright MCP server writes to ``<working_dir>/screenshots/``.
      - In Docker, ``./gui_agent_v1/screenshots`` is volume-mounted to
        ``/app/screenshots``, so files land in the agent's own folder.
      - For local (non-Docker) usage the ``screenshots/`` sub-directory
        is created relative to wherever the MCP server runs.

    Args:
        tool: The tool being called (BaseTool/McpTool instance).
        args: Mutable dict of tool arguments.
        tool_context: ADK tool context.

    Returns:
        None to proceed with (possibly modified) args.
    """
    if tool.name != "browser_take_screenshot":
        return None

    settings = get_settings()
    screenshot_dir = settings.screenshot_dir  # default: "screenshots"
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")

    original = args.get("filename")
    if original:
        # Strip any directory prefix the LLM might have added
        base = original.rsplit("/", 1)[-1]
        base = _sanitize_filename(base)
        # Ensure it has an extension
        if "." not in base:
            base = f"{base}.png"
        args["filename"] = f"{screenshot_dir}/{timestamp}_{base}"
    else:
        # No filename provided — create a descriptive default
        args["filename"] = f"{screenshot_dir}/{timestamp}_screenshot.png"

    logger.debug(f"Screenshot will be saved as: {args['filename']}")
    return None


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------

def create_playwright_toolset() -> McpToolset:
    """Create the Playwright MCP toolset.

    Uses the official @playwright/mcp package which uses a ref-based approach:
    1. Call browser_snapshot to get accessibility tree with element refs
    2. Use ref parameter in subsequent tool calls (e.g., ref="e1")

    Returns:
        McpToolset configured to connect to the Playwright MCP server.
    """
    settings = get_settings()

    return McpToolset(
        connection_params=SseConnectionParams(
            url=settings.playwright_mcp_url,
        ),
        # Filter to tools available in @playwright/mcp
        # See: https://github.com/microsoft/playwright-mcp
        tool_filter=[
            # Navigation
            "browser_navigate",
            "browser_go_back",
            "browser_go_forward",
            # Page state & content
            "browser_snapshot",      # Returns accessibility tree with refs [ref=e1]
            "browser_take_screenshot",
            # Interactions (all use ref parameter from snapshot)
            "browser_click",
            "browser_type",
            "browser_hover",
            "browser_select_option",  # For dropdowns
            "browser_press_key",
            # Utilities
            "browser_wait_for",
        ],
    )


def create_form_filling_agent(
    toolset: McpToolset | None = None,
    model: str | None = None,
) -> LlmAgent:
    """Create the form-filling agent.

    Args:
        toolset: Optional pre-configured toolset. If None, creates default.
        model: Optional model override. Defaults to settings.

    Returns:
        Configured LlmAgent for form filling tasks.
    """
    settings = get_settings()

    if toolset is None:
        toolset = create_playwright_toolset()

    return LlmAgent(
        name="form_filling_agent",
        model=model or settings.model_name,
        instruction=FORM_FILLING_SYSTEM_PROMPT,
        tools=[toolset],
        before_tool_callback=_screenshot_callback,
    )


# ---------------------------------------------------------------------------
# ADK CLI discovery
# ---------------------------------------------------------------------------
# `adk web`, `adk run`, and `adk eval` all expect a module-level variable
# named exactly `root_agent` that IS an LlmAgent instance — not a function,
# not a property descriptor, not None.
#
# McpToolset uses lazy connection (constructed here, connects later when
# tools are actually invoked), so this is safe to run at import time even
# when the Playwright MCP server is not yet running.
# ---------------------------------------------------------------------------
_settings = get_settings()
_settings.configure_environment()

# Set up Arize Phoenix tracing BEFORE creating the agent.
# This is critical: instrumentation must be registered before any ADK
# objects are used, so traces are captured for ALL entry points
# (adk web, adk run, adk eval, and the CLI).
_tracing_provider = setup_tracing(_settings)
if _tracing_provider:
    setup_adk_instrumentation(_tracing_provider)

root_agent = create_form_filling_agent()

logger.info(f"Created root agent with model: {_settings.model_name}")
logger.info(f"Authentication mode: {_settings.auth_mode}")


async def run_agent_task(
    task: str,
    user_id: str = "default_user",
    session_id: str | None = None,
) -> str:
    """Run the agent on a specific task.

    Reuses the module-level ``root_agent`` so that the underlying
    McpToolset (and its SSE connection to the Playwright MCP server)
    persists across calls.  Creating a *new* agent per call would open
    a fresh SSE connection each time while the old one stays alive,
    causing "isolated browser" / "browser already in use" errors on
    repeated runs.

    Args:
        task: The task description (e.g., "Fill the contact form with...")
        user_id: User identifier for session tracking.
        session_id: Optional session ID for conversation continuity.

    Returns:
        The agent's final response.
    """
    settings = get_settings()
    settings.configure_environment()

    # Create session service
    session_service = InMemorySessionService()

    # Generate session ID if not provided
    if session_id is None:
        import uuid

        session_id = str(uuid.uuid4())

    # Create session (async in newer ADK versions)
    await session_service.create_session(
        app_name="gui-agent",
        user_id=user_id,
        session_id=session_id,
    )

    # Reuse the module-level root_agent so we keep a single SSE
    # connection to the Playwright MCP server across tasks.
    runner = Runner(
        agent=root_agent,
        app_name="gui-agent",
        session_service=session_service,
    )

    logger.info(f"Starting task: {task[:100]}...")

    # Run with tracing
    # runner.run_async returns an async generator, iterate over it
    # Create Content object from task string
    user_message = types.Content(
        role="user",
        parts=[types.Part(text=task)]
    )

    with TracingContext(settings):
        final_response = ""
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_message,
        ):
            # Extract text from various event types
            if hasattr(event, "content") and event.content:
                if hasattr(event.content, "parts"):
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            final_response = part.text
                elif hasattr(event.content, "text"):
                    final_response = event.content.text

    logger.info(f"Task completed. Response length: {len(final_response)}")
    return final_response


def run_task_sync(task: str, user_id: str = "default_user") -> str:
    """Synchronous wrapper for run_agent_task.

    Args:
        task: The task description.
        user_id: User identifier.

    Returns:
        The agent's final response.
    """
    return asyncio.run(run_agent_task(task, user_id))


if __name__ == "__main__":
    # Simple test when run directly
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
    else:
        task = "Take a screenshot of https://example.com and describe what you see"

    print(f"Running task: {task}")
    result = run_task_sync(task)
    print(f"Result: {result}")
