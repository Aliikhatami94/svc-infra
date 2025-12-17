from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from svc_infra.billing import BillingService
from svc_infra.billing.models import (
    Invoice,
    InvoiceLine,
    Plan,
    PlanEntitlement,
    Price,
    Subscription,
    UsageAggregate,
    UsageEvent,
)
from svc_infra.db.sql.base import ModelBase


@pytest.fixture()
def sync_session():
    engine = create_engine("sqlite:///:memory:")
    # create only billing tables to avoid FKs from unrelated models
    tables = [
        UsageEvent.__table__,
        UsageAggregate.__table__,
        Plan.__table__,
        PlanEntitlement.__table__,
        Subscription.__table__,
        Price.__table__,
        Invoice.__table__,
        InvoiceLine.__table__,
    ]
    ModelBase.metadata.create_all(engine, tables=tables)
    s = Session(engine)
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


def test_record_and_aggregate_and_invoice(sync_session: Session):
    # Using a lightweight sync session for unit test simplicity
    # Arrange
    tenant = "t_123"
    bs = BillingService(session=sync_session, tenant_id=tenant)
    now = datetime(2025, 1, 1, 10, tzinfo=timezone.utc)

    # Act: record usage
    evt_id = bs.record_usage(metric="tokens", amount=5, at=now, idempotency_key="k1", metadata=None)
    assert evt_id

    # Aggregate
    bs.aggregate_daily(
        metric="tokens",
        day_start=now.replace(hour=0, minute=0, second=0, microsecond=0),
    )

    # Generate invoice for month
    period_start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    period_end = datetime(2025, 2, 1, tzinfo=timezone.utc)
    inv_id = bs.generate_monthly_invoice(
        period_start=period_start, period_end=period_end, currency="usd"
    )
    assert inv_id

    # Assert rows exist
    events = sync_session.query(UsageEvent).all()
    assert len(events) == 1
    aggs = sync_session.query(UsageAggregate).all()
    assert len(aggs) == 1
    assert int(aggs[0].total) == 5
    inv = sync_session.query(Invoice).first()
    assert inv is not None
    assert int(inv.total_amount) == 5
    lines = sync_session.query(InvoiceLine).all()
    assert len(lines) == 1


def test_provider_sync_called(sync_session: Session):
    tenant = "t_sync"
    hook = Mock()
    bs = BillingService(session=sync_session, tenant_id=tenant, provider_sync=hook)
    now = datetime(2025, 1, 5, tzinfo=timezone.utc)

    bs.record_usage(metric="req", amount=2, at=now, idempotency_key="x", metadata=None)
    bs.aggregate_daily(
        metric="req", day_start=now.replace(hour=0, minute=0, second=0, microsecond=0)
    )
    bs.generate_monthly_invoice(
        period_start=datetime(2025, 1, 1, tzinfo=timezone.utc),
        period_end=datetime(2025, 2, 1, tzinfo=timezone.utc),
        currency="usd",
    )
    hook.assert_called_once()


def test_idempotency_unique(sync_session: Session):
    tenant = "t_idem"
    bs = BillingService(session=sync_session, tenant_id=tenant)
    now = datetime(2025, 1, 7, tzinfo=timezone.utc)
    bs.record_usage(metric="x", amount=1, at=now, idempotency_key="dup", metadata=None)
    with pytest.raises(IntegrityError):
        # second with same idempotency should violate unique constraint on flush
        bs.record_usage(metric="x", amount=1, at=now, idempotency_key="dup", metadata=None)
        sync_session.commit()
