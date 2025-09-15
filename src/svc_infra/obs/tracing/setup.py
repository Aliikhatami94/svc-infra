from __future__ import annotations

import atexit
import os
import uuid
from typing import Any, Callable, Dict, List

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as OTLPgExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as OTLPhttpExporter,
)
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

# Try to load propagators defensively; not all installs ship all extras.
_available_propagators: List[object] = []
try:
    from opentelemetry.propagators.tracecontext import (  # type: ignore[attr-defined]
        TraceContextTextMapPropagator,
    )

    _available_propagators.append(TraceContextTextMapPropagator())
except Exception:
    pass
try:
    from opentelemetry.propagators.baggage import W3CBaggagePropagator  # type: ignore[attr-defined]

    _available_propagators.append(W3CBaggagePropagator())
except Exception:
    pass
try:
    # B3 is in a separate package in many installs; guard it.
    from opentelemetry.propagators.b3 import B3MultiFormat

    _available_propagators.append(B3MultiFormat())
except Exception:
    pass

# Fallback: if nothing loaded, at least keep W3C tracecontext via API default.
if not _available_propagators:
    try:
        from opentelemetry.propagators.tracecontext import (  # type: ignore[attr-defined]
            TraceContextTextMapPropagator,
        )

        _available_propagators.append(TraceContextTextMapPropagator())
    except Exception:
        _available_propagators = []  # let OpenTelemetry’s default remain in place


def setup_tracing(
    *,
    service_name: str,
    endpoint: str = "http://localhost:4317",
    protocol: str = "grpc",  # or "http/protobuf"
    sample_ratio: float = 0.1,
    instrument_fastapi: bool = True,
    instrument_sqlalchemy: bool = True,
    instrument_requests: bool = True,
    instrument_httpx: bool = True,
    service_version: str | None = None,
    deployment_env: str | None = None,
    headers: Dict[str, str] | None = None,
) -> Callable[..., Any]:
    """
    Initialize OpenTelemetry tracing + common instrumentations.

    Returns:
        shutdown() -> None : flushes spans/exporters; call this on app shutdown.
    """
    # --- Resource attributes (semantic conventions)
    attrs = {
        "service.name": service_name,
        "service.version": service_version or os.getenv("SERVICE_VERSION") or "unknown",
        "deployment.environment": deployment_env or os.getenv("DEPLOYMENT_ENV") or "dev",
        "service.instance.id": os.getenv("HOSTNAME") or str(uuid.uuid4()),
    }
    resource = Resource.create({k: v for k, v in attrs.items() if v is not None})

    provider = TracerProvider(
        resource=resource,
        sampler=ParentBased(TraceIdRatioBased(sample_ratio)),
    )
    trace.set_tracer_provider(provider)

    # --- Exporter
    if protocol == "grpc":
        exporter = OTLPgExporter(endpoint=endpoint, insecure=True, headers=headers)
    else:
        http_endpoint = endpoint.replace(":4317", ":4318")
        exporter = OTLPhttpExporter(endpoint=http_endpoint, headers=headers)

    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)

    # --- Propagators (use whatever we could import)
    if _available_propagators:
        set_global_textmap(CompositePropagator(_available_propagators))

    # --- Auto-instrumentation (best-effort, never fail boot)
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

    # --- Shutdown hook (flush on exit)
    def shutdown() -> None:
        try:
            provider.shutdown()
        except Exception:
            pass

    atexit.register(shutdown)
    return shutdown


# Small helper for structured logs
def log_trace_context() -> dict[str, str]:
    c = trace.get_current_span().get_span_context()
    if not c.is_valid:
        return {}
    return {"trace_id": f"{c.trace_id:032x}", "span_id": f"{c.span_id:016x}"}
