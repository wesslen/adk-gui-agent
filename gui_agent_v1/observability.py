"""Observability setup for Arize Phoenix integration.

This module configures OpenTelemetry tracing to send traces to a local
Arize Phoenix instance. It uses the openinference-instrumentation-google-genai
package to automatically instrument Google GenAI (Gemini) calls.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import TYPE_CHECKING, Generator

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor

if TYPE_CHECKING:
    from gui_agent_v1.config import Settings

logger = logging.getLogger(__name__)


def setup_tracing(settings: "Settings") -> TracerProvider | None:
    """Configure OpenTelemetry tracing for Phoenix.

    Args:
        settings: Application settings containing Phoenix configuration.

    Returns:
        The configured TracerProvider, or None if tracing is disabled.
    """
    if not settings.enable_tracing:
        logger.info("Tracing is disabled")
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
    provider = TracerProvider(resource=resource)

    # Configure OTLP exporter to send traces to Phoenix
    otlp_exporter = OTLPSpanExporter(
        endpoint=settings.phoenix_collector_endpoint,
    )

    # Use BatchSpanProcessor for production, SimpleSpanProcessor for debugging
    # BatchSpanProcessor is more efficient but may delay trace visibility
    processor = BatchSpanProcessor(otlp_exporter)
    provider.add_span_processor(processor)

    # Set as global tracer provider
    trace.set_tracer_provider(provider)

    logger.info(f"Tracing configured - sending traces to {settings.phoenix_collector_endpoint}")
    logger.info(f"View traces at {settings.phoenix_ui_url}")

    return provider


def setup_genai_instrumentation() -> None:
    """Set up automatic instrumentation for Google GenAI calls.

    This instruments the google-genai library to automatically create
    spans for all Gemini API calls.
    """
    try:
        from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor

        GoogleGenAIInstrumentor().instrument()
        logger.info("Google GenAI instrumentation enabled")
    except ImportError:
        logger.warning(
            "openinference-instrumentation-google-genai not installed. "
            "Install it for automatic Gemini call tracing."
        )
    except Exception as e:
        logger.warning(f"Failed to enable GenAI instrumentation: {e}")


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

    Example:
        ```python
        settings = get_settings()
        with TracingContext(settings):
            # Run agent - all Gemini calls will be traced
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
            setup_genai_instrumentation()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Flush and shut down tracing on context exit."""
        if self.provider:
            # Force flush any pending spans
            self.provider.force_flush()
            self.provider.shutdown()
            logger.info("Tracing shut down - all spans flushed")
