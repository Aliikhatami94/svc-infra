from __future__ import annotations

from typing import Any, Mapping, Optional

from sqlalchemy.engine import Engine

try:
    from sqlalchemy.ext.asyncio import AsyncEngine
except Exception:  # optional
    AsyncEngine = None  # type: ignore

from .base import counter, gauge

_pool_in_use = gauge(
    "db_pool_in_use",
    "Checked-out connections",
    labels=["db"],
    multiprocess_mode="livesum",
)
_pool_available = gauge(
    "db_pool_available",
    "Available idle connections",
    labels=["db"],
    multiprocess_mode="livesum",
)
_pool_checked_out_total = counter("db_pool_checkedout_total", "Total checkouts", labels=["db"])
_pool_checked_in_total = counter("db_pool_checkedin_total", "Total checkins", labels=["db"])


def _label(labels: Optional[Mapping[str, str]]) -> str:
    return (labels or {}).get("db", "default")


def bind_sqlalchemy_pool_metrics(
    engine: Engine | Any, labels: Optional[Mapping[str, str]] = None
) -> None:
    """Bind event listeners for pool metrics. Works for sync Engine.
    For AsyncEngine pass engine.sync_engine."""
    label = _label(labels)
    sync_engine: Engine = getattr(engine, "sync_engine", engine)

    from sqlalchemy import event

    @event.listens_for(sync_engine, "engine_connect")
    def _(conn, branch):  # noqa
        # Update gauges on engine_connect as a cheap heartbeat
        pool = sync_engine.pool
        try:
            _pool_in_use.labels(label).set(pool.checkedout())
            _pool_available.labels(label).set(pool.size() - pool.checkedout())
        except Exception:
            pass

    @event.listens_for(sync_engine, "checkout")
    def _checkout(dbapi_con, con_record, con_proxy):  # noqa
        _pool_checked_out_total.labels(label).inc()
        try:
            pool = sync_engine.pool
            _pool_in_use.labels(label).set(pool.checkedout())
            _pool_available.labels(label).set(pool.size() - pool.checkedout())
        except Exception:
            pass

    @event.listens_for(sync_engine, "checkin")
    def _checkin(dbapi_con, con_record):  # noqa
        _pool_checked_in_total.labels(label).inc()
        try:
            pool = sync_engine.pool
            _pool_in_use.labels(label).set(pool.checkedout())
            _pool_available.labels(label).set(pool.size() - pool.checkedout())
        except Exception:
            pass
