import time

import pytest

pytestmark = pytest.mark.jobs


@pytest.fixture()
def fakeredis(monkeypatch):
    try:
        import fakeredis
    except Exception:  # pragma: no cover - dependency may not exist
        pytest.skip("fakeredis not installed")
    return fakeredis.FakeRedis()


def _clear_all(r, prefix: str = "jobs"):
    for key in r.scan_iter(f"{prefix}:*"):
        r.delete(key)


def test_enqueue_and_reserve_ack(fakeredis):
    from svc_infra.jobs.redis_queue import RedisJobQueue

    r = fakeredis
    _clear_all(r)
    q = RedisJobQueue(r, prefix="t1", visibility_timeout=5)
    job = q.enqueue("demo", {"a": 1})
    got = q.reserve_next()
    assert got is not None
    assert got.id == job.id
    assert got.name == "demo"
    q.ack(got.id)
    # no job now
    assert q.reserve_next() is None


def test_fail_backoff_and_retry(fakeredis):
    from svc_infra.jobs.redis_queue import RedisJobQueue

    r = fakeredis
    _clear_all(r)
    q = RedisJobQueue(r, prefix="t2", visibility_timeout=1)
    job = q.enqueue("demo", {"a": 2})
    # speed up retry for test
    r.hset(f"t2:job:{job.id}", mapping={"backoff_seconds": 1})
    got = q.reserve_next()
    assert got is not None
    assert got.attempts == 1
    q.fail(got.id, error="boom")
    # immediately no job available
    assert q.reserve_next() is None
    # move delayed to ready by manipulating time: advance score
    # fakeredis honors time via time.time(), so we sleep a tiny bit
    time.sleep(1.1)
    got2 = q.reserve_next()
    assert got2 is not None
    assert int(got2.attempts) == 2


def test_dlq_after_max_attempts(fakeredis):
    from svc_infra.jobs.redis_queue import RedisJobQueue

    r = fakeredis
    _clear_all(r)
    q = RedisJobQueue(r, prefix="t3", visibility_timeout=0)
    # set max_attempts=1 by direct job hash update after enqueue
    job = q.enqueue("demo", {"x": 1})
    r.hset(f"t3:job:{job.id}", mapping={"max_attempts": 1})
    got = q.reserve_next()
    assert got is not None
    # next reserve should DLQ and return None
    q.fail(got.id, error="boom")
    assert q.reserve_next() is None
    # dlq contains the id
    assert r.llen("t3:dlq") == 1
