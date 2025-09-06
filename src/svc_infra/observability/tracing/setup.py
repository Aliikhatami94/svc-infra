from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as OTLPgExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as OTLPhttpExporter
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

def setup_tracing(
        *,
        service_name: str,
        endpoint: str = "http://localhost:4317",
        protocol: str = "grpc",   # or "http/protobuf"
        sample_ratio: float = 0.1,
        instrument_fastapi: bool = True,
        instrument_sqlalchemy: bool = True,
        instrument_requests: bool = True,
        instrument_httpx: bool = True,
        service_version: str | None = None,
        deployment_env: str | None = None,
        headers: dict[str, str] | None = None
) -> None:
    """Initialize OTel tracing + common instrumentations."""
    attrs = {"service.name": service_name}
    if service_version: attrs["service.version"] = service_version
    if deployment_env:  attrs["deployment.environment"] = deployment_env
    resource = Resource.create(attrs)
    provider = TracerProvider(resource=resource, sampler=ParentBased(TraceIdRatioBased(sample_ratio)))
    trace.set_tracer_provider(provider)

    if protocol == "grpc":
        exporter = OTLPgExporter(endpoint=endpoint, insecure=True, headers=headers)
    else:
        exporter = OTLPhttpExporter(endpoint=endpoint.replace(":4317", ":4318"), headers=headers)

    provider.add_span_processor(BatchSpanProcessor(exporter))

    # Auto instrumentations (keep light + controllable)
    try:
        if instrument_fastapi:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
            FastAPIInstrumentor().instrument()
    except Exception:
        pass

    try:
        if instrument_sqlalchemy:
            from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
            SQLAlchemyInstrumentor().instrument()
    except Exception:
        pass

    try:
        if instrument_requests:
            from opentelemetry.instrumentation.requests import RequestsInstrumentor
            RequestsInstrumentor().instrument()
    except Exception:
        pass

    try:
        if instrument_httpx:
            from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
            HTTPXClientInstrumentor().instrument()
    except Exception:
        pass