from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select

from svc_infra.apf_payments.models import LedgerEntry, PayIntent
from svc_infra.apf_payments.provider.aiydan import AiydanAdapter
from svc_infra.apf_payments.schemas import (
    BalanceSnapshotOut,
    CaptureIn,
    IntentCreateIn,
    RefundIn,
    UsageRecordIn,
)
from svc_infra.apf_payments.service import PaymentsService


class DummyClient:
    def __init__(self):
        self._intents: dict[str, dict] = {}

    async def create_intent(self, payload):
        pid = "pi_test"
        obj = {
            "id": pid,
            "status": (
                "requires_capture" if payload.get("capture_method") == "manual" else "succeeded"
            ),
            "amount": payload.get("amount", 0),
            "currency": payload.get("currency", "USD"),
            "client_secret": "secret_123",
            "next_action": {"type": "redirect", "url": "https://example.com/auth"},
        }
        self._intents[pid] = obj
        return obj

    async def capture_intent(self, provider_intent_id, amount=None):
        obj = self._intents.get(provider_intent_id)
        if obj:
            obj["status"] = "succeeded"
        return obj

    async def refund_intent(self, provider_intent_id, payload):
        obj = self._intents.get(provider_intent_id)
        if obj:
            obj["status"] = "succeeded"
        return obj

    async def get_intent(self, provider_intent_id):
        return self._intents.get(provider_intent_id)

    async def get_balance_snapshot(self):
        return {
            "available": {"USD": 1000},
            "pending": [{"currency": "eur", "amount": 500}],
        }

    async def create_usage_record(self, payload):
        return {
            "id": "ur_1",
            "quantity": payload.get("quantity", 0),
            "action": payload.get("action", "increment"),
        }


class FakeSession:
    def __init__(self):
        self._rows = []

    def add(self, obj):  # sync path used in service
        # auto id assignment if missing
        if hasattr(obj, "id") and obj.id in (None, ""):
            import uuid

            obj.id = uuid.uuid4().hex[:18]
        self._rows.append(obj)

    async def flush(self):
        return None

    async def scalar(self, stmt):
        from svc_infra.apf_payments.models import LedgerEntry, PayCustomer, PayIntent

        # Determine target model of select
        target = None
        for col in getattr(stmt, "_raw_columns", []):
            ent = getattr(col, "entity", None)
            if ent is not None:
                target = ent
                break
        # Heuristic fallback if raw_columns absent
        stmt_str = str(stmt)
        if target is None:
            if "pay_intents" in stmt_str:
                target = PayIntent
            elif "ledger_entries" in stmt_str:
                target = LedgerEntry
            elif "pay_customers" in stmt_str:
                target = PayCustomer
        # Build criteria mapping
        criteria_map: dict[str, Any] = {}
        for crit in getattr(stmt, "_where_criteria", []):
            left = getattr(getattr(crit, "left", None), "name", None)
            right = getattr(getattr(crit, "right", None), "value", None)
            if left is not None:
                criteria_map[left] = right
        for row in self._rows:
            if target is PayIntent and isinstance(row, PayIntent):
                pid = criteria_map.get("provider_intent_id")
                if pid == row.provider_intent_id:
                    return row
            # Fallback: direct provider_intent_id match if PayIntent target and criteria_map empty
            if target is PayIntent and isinstance(row, PayIntent) and not criteria_map:
                # attempt substring search
                for crit in getattr(stmt, "_where_criteria", []):
                    if row.provider_intent_id in str(crit):
                        return row
            if target is LedgerEntry and isinstance(row, LedgerEntry):
                ref = criteria_map.get("provider_ref")
                kind = criteria_map.get("kind")
                if ref == row.provider_ref and kind == row.kind:
                    return row
            if target is PayCustomer and isinstance(row, PayCustomer):
                pcid = criteria_map.get("provider_customer_id")
                if pcid == row.provider_customer_id:
                    return row
        return None

    async def execute(self, stmt):
        class _Result:
            def scalars(self_inner):
                class _Scalars:
                    def all(self_s):
                        return []

                return _Scalars()

        return _Result()


@pytest.mark.asyncio
async def test_balance_snapshot_and_usage_record(mocker):
    # Setup adapter with dummy client
    adapter = AiydanAdapter(client=DummyClient())
    # Inject adapter into registry manually
    from svc_infra.apf_payments.provider.registry import get_provider_registry

    reg = get_provider_registry()
    reg.register(adapter)
    fake_session = FakeSession()
    service = PaymentsService(session=fake_session, tenant_id="tenant_x", provider_name="aiydan")

    snap = await service.get_balance_snapshot()
    assert isinstance(snap, BalanceSnapshotOut)
    assert any(a.currency == "USD" for a in snap.available)
    assert any(p.currency == "EUR" for p in snap.pending)

    usage = await adapter.create_usage_record(UsageRecordIn(quantity=5))
    assert usage.action == "increment"


@pytest.mark.asyncio
async def test_tenant_persistence_and_ledger(mocker):
    adapter = AiydanAdapter(client=DummyClient())
    from svc_infra.apf_payments.provider.registry import get_provider_registry

    reg = get_provider_registry()
    reg.register(adapter)
    fake_session = FakeSession()
    service = PaymentsService(session=fake_session, tenant_id="tenant_y", provider_name="aiydan")

    intent_out = await service.create_intent(
        user_id=None, data=IntentCreateIn(amount=1000, currency="USD")
    )
    await fake_session.flush()
    row = await fake_session.scalar(
        select(PayIntent).where(PayIntent.provider_intent_id == intent_out.provider_intent_id)
    )
    assert row is not None
    assert row.tenant_id == "tenant_y"

    # capture intent should create ledger capture entry
    await service.capture_intent(intent_out.provider_intent_id, data=CaptureIn())
    await fake_session.flush()
    capture_entry = await fake_session.scalar(
        select(LedgerEntry).where(
            LedgerEntry.provider_ref == intent_out.provider_intent_id,
            LedgerEntry.kind == "capture",
        )
    )
    assert capture_entry is not None
    assert capture_entry.tenant_id == "tenant_y"

    # refund intent should create ledger refund entry
    await service.refund(intent_out.provider_intent_id, data=RefundIn(amount=500))
    await fake_session.flush()
    refund_entry = await fake_session.scalar(
        select(LedgerEntry).where(
            LedgerEntry.provider_ref == intent_out.provider_intent_id,
            LedgerEntry.kind == "refund",
        )
    )
    assert refund_entry is not None
    assert refund_entry.amount == 500
