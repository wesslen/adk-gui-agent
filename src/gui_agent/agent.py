"""ADK Agent definition for GUI automation.

This module defines the root_agent that ADK discovers and uses for
form-filling tasks with Playwright MCP tools.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.mcp_tool import McpToolset, SseConnectionParams
from google.genai import types

from gui_agent.config import get_settings
from gui_agent.observability import TracingContext
from gui_agent.prompts import FORM_FILLING_SYSTEM_PROMPT

if TYPE_CHECKING:
    from google.adk.agents import Agent

logger = logging.getLogger(__name__)


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
            "browser_screenshot",
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
    )


# The root_agent is discovered by ADK CLI tools (adk web, adk run, etc.)
# It's created lazily to allow configuration before instantiation
_root_agent: LlmAgent | None = None


def get_root_agent() -> LlmAgent:
    """Get or create the root agent.

    This function ensures settings are configured before creating the agent.

    Returns:
        The configured root agent.
    """
    global _root_agent

    if _root_agent is None:
        settings = get_settings()
        settings.configure_environment()
        _root_agent = create_form_filling_agent()
        logger.info(f"Created root agent with model: {settings.model_name}")
        logger.info(f"Authentication mode: {settings.auth_mode}")

    return _root_agent


# For ADK CLI discovery - this is the canonical agent export
root_agent = property(lambda self: get_root_agent())


async def run_agent_task(
    task: str,
    user_id: str = "default_user",
    session_id: str | None = None,
) -> str:
    """Run the agent on a specific task.

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

    # Create agent and runner
    agent = create_form_filling_agent()
    runner = Runner(
        agent=agent,
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
