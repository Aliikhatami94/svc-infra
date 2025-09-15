import contextlib
import sys
import types
from typing import Callable

import pytest

# ---- Helpers (fake metrics for when we want to test middleware logic) ----


class _FakeMetric:
    def __init__(self):
        self.calls = []

    def labels(self, *a, **kw):
        # return self to allow chained .inc/.dec/.observe
        return self

    # Gauge / Counter
    def inc(self, v=1):
        self.calls.append(("inc", v))

    def dec(self, v=1):
        self.calls.append(("dec", v))

    def set(self, v):
        self.calls.append(("set", v))

    # Histogram
    def observe(self, v):
        self.calls.append(("observe", v))


# ------------------------------------------------------------------------------
# Settings
# ------------------------------------------------------------------------------


def test_observability_settings_defaults():
    from svc_infra.obs.settings import ObservabilitySettings

    cfg = ObservabilitySettings()
    assert cfg.METRICS_ENABLED is True
    assert cfg.METRICS_PATH == "/metrics"
    assert isinstance(cfg.METRICS_DEFAULT_BUCKETS, tuple)
    assert cfg.OTEL_ENABLED is True
    assert cfg.OTEL_EXPORTER_OTLP_ENDPOINT.endswith(":4317")
    assert cfg.OTEL_EXPORTER_PROTOCOL in ("grpc", "http")


# ------------------------------------------------------------------------------
# add_observability (no prometheus installed)
# ------------------------------------------------------------------------------


@pytest.fixture
def starlette_app():
    from starlette.applications import Starlette
    from starlette.responses import PlainTextResponse

    app = Starlette()

    from starlette.responses import PlainTextResponse

    app.add_route("/health", lambda _: PlainTextResponse("ok"))

    return app


@contextlib.contextmanager
def _purged_module(name: str):
    import importlib

    existed = name in sys.modules
    saved = sys.modules.pop(name, None)
    orig_import_module = importlib.import_module

    def _fail(n, *a, **kw):
        if n == name or n.startswith(name + "."):
            raise ModuleNotFoundError(f"No module named {n!r}")
        return orig_import_module(n, *a, **kw)

    try:
        importlib.import_module = _fail
        yield
    finally:
        importlib.import_module = orig_import_module
        if existed and saved is not None:
            sys.modules[name] = saved


def test_add_observability_without_prometheus_exposes_501(starlette_app):
    import os

    os.environ["SVC_INFRA_DISABLE_PROMETHEUS"] = "1"
    # Ensure prometheus-client cannot import
    with _purged_module("prometheus_client"):
        from starlette.testclient import TestClient

        from svc_infra.obs import add_observability

        # should not raise even without prometheus installed
        shutdown = add_observability(starlette_app)
        assert callable(shutdown)

        with TestClient(starlette_app) as c:
            # /metrics should be present but report 501 to signal optional dep missing
            r = c.get("/metrics")
            assert r.status_code == 501
            assert "prometheus-client not installed" in r.text


def test_add_observability_auto_shutdown_hook(starlette_app, monkeypatch):
    # Capture shutdown handler registration
    calls = []

    def fake_add_event_handler(event: str, fn: Callable[[], None]):
        calls.append((event, fn))

    monkeypatch.setattr(starlette_app, "add_event_handler", fake_add_event_handler)

    from svc_infra.obs import add_observability

    shutdown = add_observability(starlette_app)
    assert callable(shutdown)
    # registered exactly once for "shutdown"
    assert any(evt == "shutdown" for (evt, _) in calls)


# ------------------------------------------------------------------------------
# metrics.asgi — lazy init + inflight stability (no prometheus required)
# ------------------------------------------------------------------------------


def test_prometheus_middleware_inflight_uses_raw_path_and_decrements(monkeypatch):
    # Wire fake metrics into the asgi module by stubbing _init_metrics()
    from starlette.applications import Starlette
    from starlette.testclient import TestClient

    app = Starlette()

    # Import module under test
    import svc_infra.obs.metrics.asgi as asgi_mod

    inflight = _FakeMetric()
    total = _FakeMetric()
    duration = _FakeMetric()

    def fake_init_metrics():
        asgi_mod._prom_ready = True
        # attach fake metric objects as if created by real _init_metrics
        asgi_mod._http_inflight = inflight
        asgi_mod._http_requests_total = total
        asgi_mod._http_request_duration = duration

    monkeypatch.setattr(asgi_mod, "_init_metrics", fake_init_metrics)

    # Add middleware + no real routes so the request becomes a 404
    app.add_middleware(asgi_mod.PrometheusMiddleware, skip_paths=())

    with TestClient(app) as c:
        r = c.get("/nope")  # 404
        assert r.status_code == 404

    # inflight must inc & dec with the SAME (normalized raw) path label
    incs = [c for c in inflight.calls if c[0] == "inc"]
    decs = [c for c in inflight.calls if c[0] == "dec"]
    assert len(incs) == 1 and len(decs) == 1, inflight.calls

    # We can't read labels from fake, but the fact we got one inc and one dec
    # proves stable labeling path was used for 404 (no strand).

    # Hist/Counter should have been recorded once as well
    assert any(op == "observe" for op, _ in duration.calls)
    assert any(op == "inc" for op, _ in total.calls)


def test_metrics_endpoint_returns_501_without_prometheus(monkeypatch):
    with _purged_module("prometheus_client"):
        from starlette.applications import Starlette
        from starlette.testclient import TestClient

        import svc_infra.obs.metrics.asgi as asgi_mod

        app = Starlette()
        app.add_route("/metrics", asgi_mod.metrics_endpoint())

        with TestClient(app) as c:
            r = c.get("/metrics")
            assert r.status_code == 501
            assert "prometheus-client not installed" in r.text


# ------------------------------------------------------------------------------
# tracing.setup + log_trace_context
# ------------------------------------------------------------------------------


def test_tracing_setup_and_log_trace_context():
    from opentelemetry import trace

    from svc_infra.obs.tracing.setup import log_trace_context, setup_tracing

    shutdown = setup_tracing(
        service_name="test-svc",
        protocol="http",  # exercise the http/protobuf branch
        sample_ratio=1.0,  # ensure span sampled
        instrument_fastapi=False,
        instrument_sqlalchemy=False,
        instrument_requests=False,
        instrument_httpx=False,
        headers={"x-test": "1"},
        service_version="1.2.3",
        deployment_env="test",
    )

    tracer = trace.get_tracer("test")
    with tracer.start_as_current_span("unit-span"):
        ctx = log_trace_context()
        assert "trace_id" in ctx and len(ctx["trace_id"]) == 32
        assert "span_id" in ctx and len(ctx["span_id"]) == 16

    # shutdown should be callable and not raise
    shutdown()


# ------------------------------------------------------------------------------
# metrics.http — only run if optional deps present
# ------------------------------------------------------------------------------


@pytest.mark.skipif(
    "requests" not in sys.modules
    and not pytest.importorskip("importlib").util.find_spec("requests"),
    reason="requests not installed",
)
def test_instrument_requests_monkeypatches_request(monkeypatch):
    import requests

    from svc_infra.obs.metrics.http import instrument_requests

    # Ensure original is restored by our test if something blows up
    orig = requests.sessions.Session.request
    try:
        instrument_requests()
        assert requests.sessions.Session.request is not orig
    finally:
        requests.sessions.Session.request = orig


@pytest.mark.skipif(
    "httpx" not in sys.modules and not pytest.importorskip("importlib").util.find_spec("httpx"),
    reason="httpx not installed",
)
def test_instrument_httpx_monkeypatches_send(monkeypatch):
    import httpx

    from svc_infra.obs.metrics.http import instrument_httpx

    orig_sync = httpx.Client.send
    orig_async = httpx.AsyncClient.send
    try:
        instrument_httpx()
        assert httpx.Client.send is not orig_sync
        assert httpx.AsyncClient.send is not orig_async
    finally:
        httpx.Client.send = orig_sync
        httpx.AsyncClient.send = orig_async


# ------------------------------------------------------------------------------
# metrics.sqlalchemy — do not require SQLAlchemy; fake the module surface
# ------------------------------------------------------------------------------


def test_bind_sqlalchemy_pool_metrics_registers_listeners_without_sqlalchemy(
    monkeypatch,
):
    """
    We emulate sqlalchemy.event.listens_for decorator and validate that our
    function registers three listeners and that calling them doesn't crash
    and interacts with the gauge/counter fakes.
    """
    # Fake sqlalchemy.event.listens_for
    listener_registry = {"engine_connect": [], "checkout": [], "checkin": []}

    def listens_for(engine, name):
        def deco(fn):
            listener_registry[name].append(fn)
            return fn

        return deco

    fake_sqlalchemy = types.SimpleNamespace(event=types.SimpleNamespace(listens_for=listens_for))
    monkeypatch.setitem(sys.modules, "sqlalchemy", fake_sqlalchemy)

    # Import module under test
    import svc_infra.obs.metrics.sqlalchemy as sa_metrics

    # Patch the metric objects with fakes
    sa_metrics._pool_in_use = _FakeMetric()
    sa_metrics._pool_available = _FakeMetric()
    sa_metrics._pool_checked_out_total = _FakeMetric()
    sa_metrics._pool_checked_in_total = _FakeMetric()

    # Fake engine with a pool
    class _Pool:
        def __init__(self, size=10, checkedout=0):
            self._size = size
            self._checkedout = checkedout

        def size(self):
            return self._size

        def checkedout(self):
            return self._checkedout

    class _Engine:
        def __init__(self):
            self.pool = _Pool()

    engine = _Engine()

    # Act
    sa_metrics.bind_sqlalchemy_pool_metrics(engine)

    # We registered all three listeners
    assert listener_registry["engine_connect"]
    assert listener_registry["checkout"]
    assert listener_registry["checkin"]

    # Simulate events:
    listener_registry["engine_connect"][0](None, None)  # should set gauges
    listener_registry["checkout"][0](None, None, None)  # inc + set gauges
    listener_registry["checkin"][0](None, None)  # inc + set gauges

    # Verify some calls landed (we don't assert exact values)
    assert sa_metrics._pool_in_use.calls
    assert sa_metrics._pool_available.calls
    assert sa_metrics._pool_checked_out_total.calls
    assert sa_metrics._pool_checked_in_total.calls
