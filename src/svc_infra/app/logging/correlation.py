from __future__ import annotations

import logging

try:
    from opentelemetry.trace import get_current_span
except Exception:  # otel not installed: make filter a no-op

    def get_current_span():
        return None  # type: ignore


class OTelTraceContextFilter(logging.Filter):
    """Attach trace_id/span_id to LogRecord if an OTel span is active."""

    def filter(self, record: logging.LogRecord) -> bool:
        span = get_current_span()
        ctx = getattr(span, "get_span_context", lambda: None)()
        if ctx and getattr(ctx, "is_valid", False):
            record.trace_id = f"{ctx.trace_id:032x}"
            record.span_id = f"{ctx.span_id:016x}"
        else:
            record.trace_id = None
            record.span_id = None
        return True
