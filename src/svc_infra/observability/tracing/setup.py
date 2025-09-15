from __future__ import annotations

import atexit
import os
import uuid
from typing import Any, Callable, Dict, List, Mapping, Optional

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as OTLPHTTPExporter,
)
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

# -------------------- propagators (best-effort) --------------------

_available_propagators: List[object] = []
try:
    from opentelemetry.propagators.tracecontext import (
        TraceContextTextMapPropagator,  # type: ignore[attr-defined]
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
    from opentelemetry.propagators.b3 import B3MultiFormat

    _available_propagators.append(B3MultiFormat())
except Exception:
    pass

if not _available_propagators:
    try:
        from opentelemetry.propagators.tracecontext import (
            TraceContextTextMapPropagator,  # type: ignore[attr-defined]
        )

        _available_propagators.append(TraceContextTextMapPropagator())
    except Exception:
        _available_propagators = []


# -------------------- helpers --------------------


def _env_protocol() -> str:
    """
    Resolve OTLP protocol. Prefer function arg; otherwise env var; default to HTTP.
    Accepts values like "http", "http/protobuf", "grpc".
    """
    raw = (os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL") or "").strip().lower()
    if raw in {"http", "http/protobuf", "http_json"}:
        return "http/protobuf"  # we standardize on http/protobuf
    if raw == "grpc":
        return "grpc"
    return "http/protobuf"


def _normalize_protocol(protocol: Optional[str]) -> str:
    if protocol:
        p = protocol.strip().lower()
        if p in {"http", "http/protobuf"}:
            return "http/protobuf"
        if p == "grpc":
            return "grpc"
    return _env_protocol()


def _guess_endpoint(endpoint: Optional[str], protocol: str) -> str:
    """
    Pick/adjust endpoint to the conventional port:
      - http → 4318
      - grpc → 4317
    If you pass one explicitly, we keep your scheme/host and only swap the port when it
    looks like the other protocol's default.
    """
    default_http = "http://localhost:4318"
    default_grpc = "http://localhost:4317"

    ep = (endpoint or "").strip()
    if not ep:
        return default_http if protocol == "http/protobuf" else default_grpc

    # Quick, safe port swap heuristics:
    if protocol == "http/protobuf" and ep.endswith(":4317"):
        return ep[:-5] + "4318"
    if protocol == "grpc" and ep.endswith(":4318"):
        return ep[:-5] + "4317"
    return ep


def _parse_headers(hdrs: Optional[Mapping[str, str] | Dict[str, str]]) -> Dict[str, str]:
    """
    Accept a mapping or fall back to OTEL_EXPORTER_OTLP_HEADERS env:
      e.g. "api-key=xxx,env=dev"
    """
    if hdrs:
        return dict(hdrs)
    env_raw = os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "").strip()
    if not env_raw:
        return {}
    out: Dict[str, str] = {}
    for pair in env_raw.split(","):
        if "=" in pair:
            k, v = pair.split("=", 1)
            k, v = k.strip(), v.strip()
            if k:
                out[k] = v
    return out


# -------------------- public API --------------------


def setup_tracing(
    *,
    service_name: str,
    endpoint: str | None = None,  # if None → sensible default per protocol
    protocol: str | None = None,  # "http/protobuf" (default) or "grpc"
    sample_ratio: float = 0.1,
    instrument_fastapi: bool = True,
    instrument_sqlalchemy: bool = True,
    instrument_requests: bool = True,
    instrument_httpx: bool = True,
    service_version: str | None = None,
    deployment_env: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> Callable[..., Any]:
    """
    Initialize OpenTelemetry tracing + common instrumentations.

    Defaults to OTLP over HTTP (no grpcio native deps).
    Honors OTEL_EXPORTER_OTLP_PROTOCOL and OTEL_EXPORTER_OTLP_HEADERS if provided.

    Returns:
        shutdown() -> None : flushes spans/exporters; call on app shutdown.
    """
    # --- Resource attributes
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

    # --- Exporter selection (HTTP default; gRPC only if requested)
    proto = _normalize_protocol(protocol)
    ep = _guess_endpoint(endpoint, proto)
    hdrs = _parse_headers(headers)

    if proto == "grpc":
        # Lazily import gRPC exporter so environments without grpcio don't crash at import time
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter as OTLPGRPCExporter,  # type: ignore
            )
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "Requested protocol='grpc' but the gRPC exporter (grpcio) is unavailable. "
                "Switch to protocol='http/protobuf' or install grpc extras."
            ) from e

        # If your endpoint is plain http://, most collectors expect insecure=True.
        insecure = ep.startswith("http://")
        exporter = OTLPGRPCExporter(endpoint=ep, insecure=insecure, headers=hdrs or None)
    else:
        # HTTP exporter is pure-Python; safest in slim containers (e.g., Railway/Nixpacks).
        exporter = OTLPHTTPExporter(endpoint=ep, headers=hdrs or None)

    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)

    # --- Propagators
    if _available_propagators:
        set_global_textmap(CompositePropagator(_available_propagators))

    # --- Auto-instrumentation (best-effort)
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

    # --- Shutdown hook
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
