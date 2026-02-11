"""Observability setup for Arize Phoenix integration.

This module configures OpenTelemetry tracing to send traces to a local
Arize Phoenix instance. It uses the openinference-instrumentation-google-adk
package to automatically instrument ADK agent execution — capturing agent
steps, tool calls, LLM interactions, and the full execution trace.

Setup is idempotent: calling setup_tracing() multiple times is safe and
only the first call configures the provider.  This is critical because
agent.py initializes tracing at module level (for adk web/run/eval) and
cli.py may also attempt initialization via TracingContext.
"""

from __future__ import annotations

import atexit
import logging
from contextlib import contextmanager
from typing import TYPE_CHECKING, Generator

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

if TYPE_CHECKING:
    from gui_agent_v1.config import Settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state for idempotent initialization
# ---------------------------------------------------------------------------
_provider: TracerProvider | None = None
_initialized: bool = False


def setup_tracing(settings: "Settings") -> TracerProvider | None:
    """Configure OpenTelemetry tracing for Phoenix.

    This function is idempotent — it only configures tracing on the first
    call.  Subsequent calls return the existing provider (or None).

    Args:
        settings: Application settings containing Phoenix configuration.

    Returns:
        The configured TracerProvider, or None if tracing is disabled
        or was already initialized.
    """
    global _provider, _initialized

    if _initialized:
        logger.debug("Tracing already initialized, skipping")
        return _provider

    _initialized = True

    if not settings.enable_tracing:
        logger.info("Tracing is disabled (ENABLE_TRACING=false)")
        return None

    # Create resource with service information
    resource = Resource.create(
        {
            "service.name": "gui-agent",
            "service.version": "0.1.0",
            "deployment.environment": "development",
        }
    )

    # Create tracer provider
    _provider = TracerProvider(resource=resource)

    # Configure OTLP exporter to send traces to Phoenix
    otlp_exporter = OTLPSpanExporter(
        endpoint=settings.phoenix_collector_endpoint,
    )

    # Use SimpleSpanProcessor for immediate trace visibility in Phoenix.
    # BatchSpanProcessor is more efficient but delays trace delivery,
    # which makes debugging harder during development.
    processor = SimpleSpanProcessor(otlp_exporter)
    _provider.add_span_processor(processor)

    # Set as global tracer provider
    trace.set_tracer_provider(_provider)

    # Register cleanup handler so spans are flushed on process exit
    atexit.register(_shutdown_tracing)

    logger.info(f"Tracing configured - sending traces to {settings.phoenix_collector_endpoint}")
    logger.info(f"View traces at {settings.phoenix_ui_url}")

    return _provider


def setup_adk_instrumentation(provider: TracerProvider | None = None) -> None:
    """Set up automatic instrumentation for Google ADK.

    This instruments the ADK framework to automatically create spans for
    agent execution, tool calls, LLM interactions, and handoffs.

    Uses openinference-instrumentation-google-adk (NOT google-genai),
    which captures the full ADK execution trace rather than just raw
    Gemini API calls.

    Args:
        provider: Optional TracerProvider to use.  If None, uses the
            global provider.
    """
    try:
        from openinference.instrumentation.google_adk import GoogleADKInstrumentor

        kwargs = {}
        if provider is not None:
            kwargs["tracer_provider"] = provider

        GoogleADKInstrumentor().instrument(**kwargs)
        logger.info("Google ADK instrumentation enabled (openinference-instrumentation-google-adk)")
    except ImportError:
        logger.warning(
            "openinference-instrumentation-google-adk not installed. "
            "Install it for automatic ADK tracing: "
            "pip install openinference-instrumentation-google-adk"
        )
    except Exception as e:
        logger.warning(f"Failed to enable ADK instrumentation: {e}")


def _shutdown_tracing() -> None:
    """Flush and shut down the global tracer provider.

    Registered as an atexit handler to ensure all spans are exported
    before the process exits.
    """
    global _provider
    if _provider:
        try:
            _provider.force_flush(timeout_millis=5000)
            _provider.shutdown()
            logger.info("Tracing shut down - all spans flushed")
        except Exception as e:
            logger.warning(f"Error shutting down tracing: {e}")
        _provider = None


def get_tracer(name: str = "gui-agent") -> trace.Tracer:
    """Get a tracer instance for manual span creation.

    Args:
        name: The tracer name (typically the module name).

    Returns:
        A Tracer instance for creating spans.
    """
    return trace.get_tracer(name)


@contextmanager
def trace_operation(
    name: str,
    attributes: dict | None = None,
) -> Generator[trace.Span, None, None]:
    """Context manager for tracing an operation.

    Args:
        name: The span name.
        attributes: Optional attributes to add to the span.

    Yields:
        The active span.

    Example:
        ```python
        with trace_operation("fill_form", {"form_id": "contact"}) as span:
            # Do form filling
            span.set_attribute("fields_filled", 5)
        ```
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        yield span


def add_agent_attributes(span: trace.Span, agent_name: str, task: str) -> None:
    """Add standard agent attributes to a span.

    Args:
        span: The span to add attributes to.
        agent_name: The name of the agent.
        task: The task being performed.
    """
    span.set_attribute("agent.name", agent_name)
    span.set_attribute("agent.task", task)


def record_tool_call(
    span: trace.Span,
    tool_name: str,
    tool_input: dict | None = None,
    tool_output: str | None = None,
) -> None:
    """Record a tool call in a span.

    Args:
        span: The span to record in.
        tool_name: The name of the tool called.
        tool_input: The input to the tool (optional).
        tool_output: The output from the tool (optional).
    """
    span.set_attribute("tool.name", tool_name)
    if tool_input:
        span.set_attribute("tool.input", str(tool_input))
    if tool_output:
        span.set_attribute("tool.output", str(tool_output)[:1000])  # Truncate long outputs


class TracingContext:
    """Context manager for the complete tracing setup.

    This handles initialization and cleanup of all tracing components.
    Since setup_tracing() is idempotent, this is safe to use even when
    tracing was already initialized at module level (e.g., by agent.py).

    Example:
        ```python
        settings = get_settings()
        with TracingContext(settings):
            # Run agent - all ADK calls will be traced
            await runner.run_async(...)
        ```
    """

    def __init__(self, settings: "Settings"):
        self.settings = settings
        self.provider: TracerProvider | None = None

    def __enter__(self) -> "TracingContext":
        """Set up tracing on context entry."""
        self.provider = setup_tracing(self.settings)
        if self.provider:
            setup_adk_instrumentation(self.provider)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Flush pending spans on context exit.

        Note: We flush but do NOT shut down the provider here, because
        the module-level provider may still be needed (e.g., adk web
        keeps running).  The atexit handler handles final shutdown.
        """
        if self.provider:
            self.provider.force_flush(timeout_millis=5000)
            logger.debug("Tracing flushed pending spans")
