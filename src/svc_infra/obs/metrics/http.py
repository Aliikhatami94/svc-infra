from __future__ import annotations

import time
from urllib.parse import urlparse

from ..settings import ObservabilitySettings
from .base import counter, histogram

_obs = ObservabilitySettings()

_http_client_total = counter(
    "http_client_requests_total",
    "Total HTTP client requests",
    labels=["host", "method", "code"],
)

_http_client_duration = histogram(
    "http_client_request_duration_seconds",
    "HTTP client request duration in seconds",
    labels=["host", "method"],
    buckets=_obs.METRICS_DEFAULT_BUCKETS,
)


def _host(url: str) -> str:
    try:
        return urlparse(url).netloc or "unknown"
    except Exception:
        return "unknown"


def instrument_requests():
    """Monkey-patch requests to capture counts/latency. Lightweight and safe."""
    import requests

    _orig = requests.sessions.Session.request

    def _wrapped(self, method, url, *a, **kw):
        host = _host(url)
        method_u = (method or "GET").upper()
        start = time.perf_counter()
        try:
            resp = _orig(self, method, url, *a, **kw)
            code = str(getattr(resp, "status_code", 0))
            return resp
        except Exception:
            code = "exc"
            raise
        finally:
            elapsed = time.perf_counter() - start
            _http_client_total.labels(host, method_u, code).inc()
            _http_client_duration.labels(host, method_u).observe(elapsed)

    requests.sessions.Session.request = _wrapped  # type: ignore[attr-defined]


def instrument_httpx():
    import httpx

    _orig_sync = httpx.Client.send
    _orig_async = httpx.AsyncClient.send

    def _wrap_sync_send(send):
        def _wrapped(self, request, *a, **kw):
            host = _host(str(request.url))
            method = str(request.method or "GET").upper()
            start = time.perf_counter()
            try:
                resp = send(self, request, *a, **kw)
                code = str(resp.status_code)
                return resp
            except Exception:
                code = "exc"
                raise
            finally:
                _http_client_total.labels(host, method, code).inc()
                _http_client_duration.labels(host, method).observe(time.perf_counter() - start)

        return _wrapped

    async def _wrapped_async(self, request, *a, **kw):
        host = _host(str(request.url))
        method = str(request.method or "GET").upper()
        start = time.perf_counter()
        try:
            resp = await _orig_async(self, request, *a, **kw)
            code = str(resp.status_code)
            return resp
        except Exception:
            code = "exc"
            raise
        finally:
            _http_client_total.labels(host, method, code).inc()
            _http_client_duration.labels(host, method).observe(time.perf_counter() - start)

    httpx.Client.send = _wrap_sync_send(_orig_sync)  # type: ignore[assignment]
    httpx.AsyncClient.send = _wrapped_async  # type: ignore[assignment]
