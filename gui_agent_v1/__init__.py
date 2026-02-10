"""GUI Agent - A form-filling agent using Google ADK with Playwright MCP tools."""

__version__ = "0.1.0"

# Re-export agent submodule so ADK CLI can resolve gui_agent_v1.agent.root_agent
from . import agent  # noqa: F401
