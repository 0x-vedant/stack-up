"""Tests for nasiko.app.utils.observability.mcp_tracing — MCP tracing utilities.

Eight test cases across four layers:

  Layer 1 — Bootstrap (2 tests)
      1. test_bootstrap_mcp_tracing_creates_tracer
      2. test_bootstrap_mcp_tracing_disabled

  Layer 2 — Span creation & null safety (2 tests)
      3. test_create_tool_call_span_sets_attributes
      4. test_create_tool_call_span_null_safe

  Layer 3 — Result & error recording (2 tests)
      5. test_record_tool_result_sets_result_and_ok_status
      6. test_record_tool_error_sets_error_status

  Layer 4 — Integration & regression (2 tests)
      7. test_traceparent_propagation  (MOST IMPORTANT)
      8. test_existing_agent_tracing_not_broken

Uses InMemorySpanExporter (no real Phoenix), unittest.mock.patch for env vars.
Follows the style of tests/bridge/test_bridge_server.py.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from opentelemetry import propagate, trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from nasiko.app.utils.observability.mcp_tracing import (
    _NullSpan,
    bootstrap_mcp_tracing,
    create_tool_call_span,
    instrument_mcp_bridge,
    record_tool_error,
    record_tool_result,
)


# ═══════════════════════════════════════════════════════════════════════════
# Paths
# ═══════════════════════════════════════════════════════════════════════════

_SOURCE_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "nasiko"
    / "app"
    / "utils"
    / "observability"
)


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def otel_setup():
    """Fresh TracerProvider + InMemorySpanExporter.

    Yields ``(tracer, exporter)`` so tests can create spans and inspect them.
    The provider is shut down after the test to prevent resource leaks.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test-mcp-tracing")
    yield tracer, exporter
    provider.shutdown()


# ═══════════════════════════════════════════════════════════════════════════
#  LAYER 1: BOOTSTRAP TESTS  (2 tests)
# ═══════════════════════════════════════════════════════════════════════════


class TestBootstrapMcpTracing:
    """bootstrap_mcp_tracing() — TracerProvider creation via phoenix.otel.register."""

    @patch("nasiko.app.utils.observability.mcp_tracing.register")
    def test_bootstrap_mcp_tracing_creates_tracer(self, mock_register):
        """Call bootstrap_mcp_tracing("test-project") with a mock register().

        phoenix.otel.register is mocked to return a fake TracerProvider.
        Assert the return value is a Tracer (not None).
        """
        # register() returns a TracerProvider that supports add_span_processor
        mock_provider = MagicMock()
        mock_register.return_value = mock_provider

        result = bootstrap_mcp_tracing(
            "test-project", "http://localhost:6006/v1/traces"
        )

        # Verify register() was called with correct arguments
        mock_register.assert_called_once_with(
            project_name="test-project",
            endpoint="http://localhost:6006/v1/traces",
            auto_instrument=False,
        )

        # Verify a span processor was attached to the provider
        mock_provider.add_span_processor.assert_called_once()

        # Must return a Tracer, not None
        assert result is not None

    @patch.dict("os.environ", {"TRACING_ENABLED": "false"})
    def test_bootstrap_mcp_tracing_disabled(self):
        """Patch TRACING_ENABLED=false → returns None, phoenix never called.

        This tests the kill-switch.  When tracing is disabled, the function
        must short-circuit before ever calling register().
        """
        with patch(
            "nasiko.app.utils.observability.mcp_tracing.register"
        ) as mock_register:
            result = bootstrap_mcp_tracing("test-project")

            assert result is None
            mock_register.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════
#  LAYER 2: SPAN CREATION & NULL SAFETY  (2 tests)
# ═══════════════════════════════════════════════════════════════════════════


class TestCreateToolCallSpan:
    """create_tool_call_span() — span creation, attributes, null safety."""

    def test_create_tool_call_span_sets_attributes(self, otel_setup):
        """Create span via InMemorySpanExporter, verify all 5 MCP attributes.

        Uses create_tool_call_span(tracer, "read_file", {"path": "/tmp"},
        "github-tools", "artifact-123") and then reads the exported span.

        Attributes checked:
          - mcp.tool.name       == "read_file"
          - mcp.tool.arguments  contains "/tmp"
          - mcp.server.name     == "github-tools"
          - mcp.server.id       == "artifact-123"
          - mcp.transport       == "stdio"
        """
        tracer, exporter = otel_setup

        with create_tool_call_span(
            tracer=tracer,
            tool_name="read_file",
            arguments={"path": "/tmp"},
            server_name="github-tools",
            artifact_id="artifact-123",
        ) as span:
            pass  # attributes are set inside the context manager

        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        s = spans[0]
        assert s.name == "mcp.tool/read_file"

        attrs = dict(s.attributes)
        assert attrs["mcp.tool.name"] == "read_file"
        assert "/tmp" in attrs["mcp.tool.arguments"]
        assert attrs["mcp.server.name"] == "github-tools"
        assert attrs["mcp.server.id"] == "artifact-123"
        assert attrs["mcp.transport"] == "stdio"

    def test_create_tool_call_span_null_safe(self):
        """tracer=None → yields _NullSpan, doesn't crash.

        Also verifies that record_tool_result() and record_tool_error()
        are safe to call on a _NullSpan (no exceptions raised).
        """
        with create_tool_call_span(
            tracer=None,
            tool_name="test",
            arguments={},
            server_name="srv",
            artifact_id="id",
        ) as span:
            assert isinstance(span, _NullSpan)

            # _NullSpan methods must be callable without raising
            span.set_attribute("key", "value")
            span.set_status(StatusCode.OK)
            span.record_exception(RuntimeError("test"))

        # record_tool_result and record_tool_error on _NullSpan — must not crash
        null_span = _NullSpan()
        record_tool_result(null_span, {"content": "hello"})
        record_tool_error(null_span, Exception("fail"))


# ═══════════════════════════════════════════════════════════════════════════
#  LAYER 3: RESULT & ERROR RECORDING  (2 tests)
# ═══════════════════════════════════════════════════════════════════════════


class TestRecordToolResult:
    """record_tool_result() — sets result attribute and OK status."""

    def test_record_tool_result_sets_result_and_ok_status(self, otel_setup):
        """Create a span, call record_tool_result(span, {"content": "hello"}).

        Assert:
          - "mcp.tool.result" attribute contains "hello"
          - span status is OK
        """
        tracer, exporter = otel_setup

        with create_tool_call_span(
            tracer=tracer,
            tool_name="echo",
            arguments={"msg": "hi"},
            server_name="test-srv",
            artifact_id="art-002",
        ) as span:
            record_tool_result(span, {"content": "hello"})

        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        s = spans[0]
        assert "hello" in s.attributes["mcp.tool.result"]
        assert s.status.status_code == StatusCode.OK


class TestRecordToolError:
    """record_tool_error() — sets ERROR status and records exception."""

    def test_record_tool_error_sets_error_status(self, otel_setup):
        """Create a span, call record_tool_error(span, Exception("tool failed")).

        Assert:
          - span status is ERROR
          - exception is recorded as a span event
        """
        tracer, exporter = otel_setup
        error = Exception("tool failed")

        with create_tool_call_span(
            tracer=tracer,
            tool_name="bad_tool",
            arguments={},
            server_name="test-srv",
            artifact_id="art-003",
        ) as span:
            record_tool_error(span, error)

        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        s = spans[0]
        assert s.status.status_code == StatusCode.ERROR

        # Exception must be recorded as a span event
        exception_events = [e for e in s.events if e.name == "exception"]
        assert len(exception_events) >= 1
        assert "tool failed" in exception_events[0].attributes["exception.message"]


# ═══════════════════════════════════════════════════════════════════════════
#  LAYER 4: INTEGRATION & REGRESSION  (2 tests)
# ═══════════════════════════════════════════════════════════════════════════


class TestTraceparentPropagation:
    """W3C traceparent header propagation through the MCP bridge.

    THIS IS THE MOST IMPORTANT TEST.

    Flow simulated:
        Agent span (parent)
          └─ HTTP request with traceparent header
               └─ Bridge FastAPI (auto-instrumented, extracts header)
                    └─ span shares same trace_id as parent
    """

    def test_traceparent_propagation(self):
        """Create parent span, extract traceparent, send to bridge, verify.

        Steps:
          1. Create a parent span (simulating agent's trace) using a
             TracerProvider with InMemorySpanExporter
          2. Extract the traceparent header using opentelemetry.propagate.inject()
          3. Create a FastAPI TestClient for the bridge app
          4. POST /mcp/test-id/call with that traceparent header
          5. Bridge returns 404 (no subprocess) — that's fine
          6. Check exported spans — if any span has a parent context matching
             the injected trace ID, propagation works
        """
        pytest.importorskip(
            "opentelemetry.instrumentation.fastapi",
            reason="FastAPI instrumentor required for traceparent propagation test",
        )
        from fastapi.testclient import TestClient
        from nasiko.mcp_bridge.server import app

        # --- Setup: InMemorySpanExporter as global provider -------------------
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))

        original_provider = trace.get_tracer_provider()
        trace.set_tracer_provider(provider)

        try:
            # --- Step 1: Create parent span (simulating agent) ----------------
            agent_tracer = provider.get_tracer("test-agent")
            with agent_tracer.start_as_current_span("agent.request") as parent:
                parent_trace_id = parent.get_span_context().trace_id

                # --- Step 2: Extract traceparent header -----------------------
                carrier: dict[str, str] = {}
                propagate.inject(carrier)

            assert "traceparent" in carrier, (
                "propagate.inject() must produce a traceparent header"
            )

            # --- Step 3 & 4: Send request to bridge with traceparent ----------
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                "/mcp/test-id/call",
                json={"tool_name": "test_tool", "arguments": {}},
                headers=carrier,
            )

            # 404 expected — no bridge subprocess running for "test-id"
            assert response.status_code in (404, 500), (
                f"Expected 404 or 500, got {response.status_code}"
            )

            # --- Step 5 & 6: Verify trace context was propagated --------------
            spans = exporter.get_finished_spans()

            # Find spans that share the parent's trace_id (excluding the
            # parent span itself).  If the FastAPI instrumentor received the
            # traceparent header, its HTTP span will have the same trace_id.
            propagated = [
                s
                for s in spans
                if s.context.trace_id == parent_trace_id
                and s.name != "agent.request"
            ]

            assert len(propagated) >= 1, (
                f"No span with parent trace_id found — propagation failed.\n"
                f"Expected trace_id: {parent_trace_id:#034x}\n"
                f"Got spans: "
                f"{[(s.name, f'{s.context.trace_id:#034x}') for s in spans]}"
            )

        finally:
            trace.set_tracer_provider(original_provider)
            provider.shutdown()


class TestExistingAgentTracingNotBroken:
    """Regression: MCP tracing additions must not break existing exports.

    The observability package originally exported:
      - bootstrap_tracing    (from tracing_utils.py)
      - ObservabilityConfig  (from config.py)
      - TracingInjector      (from injector.py)

    After our changes, the MCP functions must also be exported and none of
    the originals should be missing.
    """

    def test_existing_agent_tracing_not_broken(self):
        """Assert original + MCP exports all coexist in the observability package.

        Check 1: Import bootstrap_tracing from tracing_utils — must be callable.
        Check 2: Import __init__.py — original exports (bootstrap_tracing,
                 ObservabilityConfig, TracingInjector) + new MCP exports must
                 all be present in __all__.
        """
        # ── Check 1: tracing_utils.bootstrap_tracing ─────────────────────
        try:
            from nasiko.app.utils.observability.tracing_utils import (
                bootstrap_tracing,
            )

            assert callable(bootstrap_tracing), (
                "bootstrap_tracing must be callable"
            )
        except ImportError:
            pytest.skip(
                "tracing_utils.py not present in this repo (lives in main "
                "Nasiko repo only).  Skipping tracing_utils import check."
            )

        # ── Check 2: __init__.py exports ─────────────────────────────────
        try:
            from nasiko.app.utils.observability import __all__

            # Original exports must still be present
            for name in (
                "bootstrap_tracing",
                "ObservabilityConfig",
                "TracingInjector",
            ):
                assert name in __all__, (
                    f"Original export '{name}' missing from __all__"
                )

            # New MCP exports must also be present
            for name in (
                "bootstrap_mcp_tracing",
                "instrument_mcp_bridge",
                "create_tool_call_span",
                "record_tool_result",
                "record_tool_error",
            ):
                assert name in __all__, (
                    f"MCP export '{name}' missing from __all__"
                )
        except ImportError:
            pytest.skip(
                "observability package __init__.py could not be imported "
                "(missing tracing_utils / config / injector dependencies).  "
                "Skipping __all__ verification."
            )
