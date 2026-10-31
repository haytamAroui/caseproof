"""Real in-memory OTel SDK capture: no documents, tokens, exception events or IDs."""
import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import ALWAYS_ON

from infrastructure.telemetry.operations import observe_tool


def test_success_denial_and_exceptions_record_only_closed_attributes(monkeypatch):
    provider = TracerProvider(sampler=ALWAYS_ON)
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr('infrastructure.telemetry.operations.trace.get_tracer', provider.get_tracer)
    private = 'Bearer-secret-client-quote-identity-crop'
    result = observe_tool('caseproof_export_report', lambda: {'isError': False, 'content': private})
    assert result['content'] == private
    observe_tool('caseproof_export_report', lambda: {'isError': True, 'error': private})
    def fail():
        raise ValueError(private)
    with pytest.raises(ValueError):
        observe_tool(private, fail)
    spans = exporter.get_finished_spans()
    assert len(spans) == 3
    assert all(not s.events for s in spans)
    assert private not in repr([(s.name, dict(s.attributes), s.status.description) for s in spans])
    assert spans[1].attributes['error.type'] == 'tool_error'
    assert spans[2].attributes['gen_ai.tool.name'] == 'unknown'
    provider.shutdown()
