from __future__ import annotations

import importlib
from typing import Iterable, Optional


class _MissingPrometheus(Exception):
    pass


def _require_prometheus() -> None:
    try:
        importlib.import_module("prometheus_client")
    except Exception as exc:  # pragma: no cover - optional dep path
        raise ImportError(
            "Prometheus metrics require prometheus-client. Install via 'pip install svc-infra[metrics]'."
        ) from exc


def _prom_mod():
    _require_prometheus()
    return importlib.import_module("prometheus_client")


def registry():
    """Return the current Prometheus registry, handling multiprocess mode if set.

    Uses the default global registry unless PROMETHEUS_MULTIPROC_DIR is set,
    in which case attaches a MultiProcessCollector to a fresh CollectorRegistry.
    """
    import os

    prom = _prom_mod()
    REGISTRY = getattr(prom, "REGISTRY")
    CollectorRegistry = getattr(prom, "CollectorRegistry")
    multiprocess = getattr(prom, "multiprocess", None)

    if os.environ.get("PROMETHEUS_MULTIPROC_DIR") and multiprocess is not None:
        reg = CollectorRegistry()
        multiprocess.MultiProcessCollector(reg)
        return reg
    return REGISTRY


def _mk_metric(
    ctor_name: str,
    name: str,
    doc: str,
    labels: Optional[Iterable[str]] = None,
    **kwargs,
):
    prom = _prom_mod()
    Counter = getattr(prom, "Counter")
    Gauge = getattr(prom, "Gauge")
    Histogram = getattr(prom, "Histogram")
    Summary = getattr(prom, "Summary")

    ctors = {
        "Counter": Counter,
        "Gauge": Gauge,
        "Histogram": Histogram,
        "Summary": Summary,
    }
    ctor = ctors[ctor_name]
    labelnames = list(labels) if labels else None
    metric = ctor(name, doc, labelnames=labelnames, **kwargs)
    return metric


def counter(name: str, doc: str, labels: Optional[Iterable[str]] = None):
    return _mk_metric("Counter", name, doc, labels)


def gauge(name: str, doc: str, labels: Optional[Iterable[str]] = None, **kw):
    # e.g. gauge(..., multiprocess_mode="livesum")
    return _mk_metric("Gauge", name, doc, labels, **kw)


def histogram(
    name: str,
    doc: str,
    labels: Optional[Iterable[str]] = None,
    buckets: Optional[Iterable[float]] = None,
):
    kwargs = {"buckets": list(buckets) if buckets else None}
    # Remove None so prometheus-client uses its defaults
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    return _mk_metric("Histogram", name, doc, labels, **kwargs)


def summary(name: str, doc: str, labels: Optional[Iterable[str]] = None):
    return _mk_metric("Summary", name, doc, labels)
