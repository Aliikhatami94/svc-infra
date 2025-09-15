from opentelemetry import trace


def log_trace_context() -> dict[str, str]:
    c = trace.get_current_span().get_span_context()
    if not c.is_valid:
        return {}
    return {"trace_id": f"{c.trace_id:032x}", "span_id": f"{c.span_id:016x}"}
