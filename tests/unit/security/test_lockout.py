from __future__ import annotations

from datetime import datetime, timedelta, timezone

from svc_infra.security.lockout import LockoutConfig, compute_lockout


def test_lockout_no_lock_before_threshold():
    cfg = LockoutConfig(threshold=5)
    status = compute_lockout(0, cfg=cfg)
    assert not status.locked and status.failure_count == 0
    status = compute_lockout(4, cfg=cfg)
    assert not status.locked and status.failure_count == 4


def test_lockout_at_threshold():
    cfg = LockoutConfig(threshold=5, base_cooldown_seconds=30)
    status = compute_lockout(5, cfg=cfg, now=datetime(2025, 1, 1, tzinfo=timezone.utc))
    assert status.locked
    assert status.next_allowed_at == datetime(
        2025, 1, 1, tzinfo=timezone.utc
    ) + timedelta(seconds=30)


def test_lockout_exponential_growth_and_cap():
    cfg = LockoutConfig(threshold=3, base_cooldown_seconds=10, max_cooldown_seconds=100)
    # fail_count = 3 -> exponent 0 -> 10s
    s3 = compute_lockout(3, cfg=cfg, now=datetime(2025, 1, 1, tzinfo=timezone.utc))
    assert (
        s3.next_allowed_at - datetime(2025, 1, 1, tzinfo=timezone.utc)
    ).total_seconds() == 10
    # fail_count = 4 -> exponent 1 -> 20s
    s4 = compute_lockout(4, cfg=cfg, now=datetime(2025, 1, 1, tzinfo=timezone.utc))
    assert (
        s4.next_allowed_at - datetime(2025, 1, 1, tzinfo=timezone.utc)
    ).total_seconds() == 20
    # fail_count = 7 -> exponent 4 -> 160s -> capped at 100s
    s7 = compute_lockout(7, cfg=cfg, now=datetime(2025, 1, 1, tzinfo=timezone.utc))
    assert (
        s7.next_allowed_at - datetime(2025, 1, 1, tzinfo=timezone.utc)
    ).total_seconds() == 100
