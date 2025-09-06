from __future__ import annotations

import os
import atexit
import uuid
from typing import Optional, Dict

from opentelemetry import trace
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.propagators.b3 import B3MultiFormat
from opentelemetry.propagators.tracecontext import TraceContextTextMapPropagator
from opentelemetry.propagators.baggage import W3CBaggagePropagator

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
        headers: Dict[str, str] | None = None,
) -> callable:
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
        # help de-dupe instances in backends
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
        # default OTLP/HTTP port derivation if left at the usual 4317
        http_endpoint = endpoint.replace(":4317", ":4318")
        exporter = OTLPhttpExporter(endpoint=http_endpoint, headers=headers)

    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)

    # --- Propagators (support W3C + B3 by default)
    set_global_textmap(
        CompositePropagator(
            [
                TraceContextTextMapPropagator(),
                W3CBaggagePropagator(),
                B3MultiFormat(),
            ]
        )
    )

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

    # ensure flush on interpreter exit as a backstop
    atexit.register(shutdown)

    return shutdown