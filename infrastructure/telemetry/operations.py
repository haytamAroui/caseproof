"""Opt-in OTel spans and duration metrics with closed, content-free attributes.

MCP subset pinned to semantic-conventions v1.41.0 (development); protocol hosting
is deferred. No exporter, endpoint, baggage, exception event or document capture
is installed here. The deployment owner must approve any external collector.
"""
from __future__ import annotations

from collections.abc import Callable
from time import monotonic
from typing import Any

from opentelemetry import metrics, trace
from opentelemetry.trace import Status, StatusCode

SEMCONV_VERSION = '1.41.0'
TOOLS = frozenset({'caseproof_discover_references', 'caseproof_export_report'})
ERRORS = frozenset({'access_rejected', 'content_release_not_authorized', 'canonical_report_unavailable'})


def observe_tool(name: str, execute: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    # Never use caller-provided labels or arbitrary exception strings as attributes.
    tool = name if type(name) is str and name in TOOLS else 'unknown'
    attributes = {'mcp.method.name': 'tools/call', 'gen_ai.tool.name': tool,
                  'caseproof.telemetry.schema': 'operations-v1',
                  'caseproof.semconv.version': SEMCONV_VERSION}
    tracer = trace.get_tracer('caseproof.mcp', '1', schema_url=f'https://opentelemetry.io/schemas/{SEMCONV_VERSION}')
    histogram = metrics.get_meter('caseproof.mcp', '1').create_histogram(
        'mcp.server.operation.duration', unit='s', description='Read-only tool operation duration')
    started = monotonic()
    outcome = 'error'
    with tracer.start_as_current_span(f'tools/call {tool}', attributes=attributes,
                                     record_exception=False, set_status_on_exception=False) as span:
        try:
            result = execute()
            outcome = 'denied' if result.get('isError') else 'success'
            span.set_attribute('caseproof.outcome', outcome)
            if outcome == 'denied':
                error = result.get('error')
                span.set_attribute('error.type', error if type(error) is str and error in ERRORS else 'tool_error')
                span.set_status(Status(StatusCode.ERROR))
            return result
        except Exception:
            # Mark only the class of operation failure; never record the exception.
            span.set_attribute('error.type', 'contract_or_execution_error')
            span.set_status(Status(StatusCode.ERROR))
            raise
        finally:
            histogram.record(monotonic() - started, {'gen_ai.tool.name': tool, 'caseproof.outcome': outcome})
