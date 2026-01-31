"""Command-line interface for the GUI agent."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from gui_agent.agent import run_agent_task
from gui_agent.config import get_settings
from gui_agent.observability import TracingContext


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the CLI."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def print_config(settings) -> None:
    """Print current configuration."""
    print("\n" + "=" * 60)
    print("GUI Agent Configuration")
    print("=" * 60)
    print(settings)
    print("=" * 60 + "\n")


async def interactive_mode() -> None:
    """Run the agent in interactive mode."""
    settings = get_settings()
    settings.configure_environment()

    print("\n🤖 GUI Agent Interactive Mode")
    print("-" * 40)
    print(f"Model: {settings.model_name}")
    print(f"Auth: {settings.auth_mode}")
    print(f"Playwright MCP: {settings.playwright_mcp_url}")
    print(f"Phoenix UI: {settings.phoenix_ui_url}")
    print("-" * 40)
    print("Type 'quit' or 'exit' to stop")
    print("Type 'config' to show configuration")
    print()

    with TracingContext(settings):
        while True:
            try:
                task = input("📝 Enter task: ").strip()

                if not task:
                    continue

                if task.lower() in ("quit", "exit", "q"):
                    print("Goodbye!")
                    break

                if task.lower() == "config":
                    print_config(settings)
                    continue

                print("\n⏳ Processing...\n")
                result = await run_agent_task(task)
                print(f"\n✅ Result:\n{result}\n")

            except KeyboardInterrupt:
                print("\n\nInterrupted. Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}\n")


async def single_task_mode(task: str) -> None:
    """Run a single task and exit."""
    settings = get_settings()
    settings.configure_environment()

    with TracingContext(settings):
        result = await run_agent_task(task)
        print(result)


def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="GUI Agent - Form-filling automation with ADK",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode
  gui-agent

  # Run a single task
  gui-agent --task "Navigate to example.com and take a screenshot"

  # Show configuration
  gui-agent --config

  # Verbose output
  gui-agent -v
        """,
    )

    parser.add_argument(
        "-t",
        "--task",
        type=str,
        help="Run a single task and exit",
    )

    parser.add_argument(
        "-c",
        "--config",
        action="store_true",
        help="Show configuration and exit",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    setup_logging(args.verbose)

    try:
        settings = get_settings()
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        print("\nPlease check your .env file or environment variables.")
        sys.exit(1)

    if args.config:
        print_config(settings)
        sys.exit(0)

    if args.task:
        asyncio.run(single_task_mode(args.task))
    else:
        asyncio.run(interactive_mode())


if __name__ == "__main__":
    main()
