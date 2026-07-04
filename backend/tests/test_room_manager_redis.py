"""
Proves RedisRoomManager's actual value proposition: TWO INDEPENDENT instances (each
with their own local socket registry, standing in for two separate backend processes)
correctly share room membership and relay messages between each other — all through
real Redis (redis://localhost:6379/0 must be reachable for these tests to run).

Uses fake sockets (plain objects recording what they were sent) rather than real
WebSockets, since we're testing the manager's logic, not FastAPI's WebSocket handling
— that part is already covered by test_rooms.py against InMemoryRoomManager, and the
router code path (rooms.py) is identical for both backends.
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
import redis.asyncio as aioredis

from app.services.room_manager import RedisRoomManager

REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/0")


def _redis_available() -> bool:
    try:
        import redis as redis_sync
        return bool(redis_sync.from_url(REDIS_URL).ping())
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _redis_available(), reason="Redis not reachable at " + REDIS_URL)


class FakeSocket:
    def __init__(self, name: str = ""):
        self.name = name
        self.received: list[dict] = []

    async def send_json(self, data: dict) -> None:
        self.received.append(data)


@pytest.fixture(autouse=True)
def _clean_redis():
    """Flush test-relevant keys before each test so tests don't see each other's rooms."""
    async def _flush():
        client = aioredis.from_url(REDIS_URL, decode_responses=True)
        keys = await client.keys("room-peers:test-*")
        if keys:
            await client.delete(*keys)
        await client.aclose()

    asyncio.run(_flush())
    yield


def _run(scenario_factory):
    """
    Runs an async scenario that receives a `make_manager()` factory, and closes every
    manager it created afterward — keeps connection cleanup out of every individual
    test. Plain asyncio.run (no pytest-asyncio) — see test_rooms.py's history for why
    that plugin is avoided in this suite.
    """
    async def runner():
        managers: list[RedisRoomManager] = []

        def make_manager() -> RedisRoomManager:
            m = RedisRoomManager(redis_url=REDIS_URL)
            managers.append(m)
            return m

        try:
            await scenario_factory(make_manager)
        finally:
            for m in managers:
                await m.close()

    asyncio.run(runner())


async def _wait_until(predicate, timeout: float = 3.0, interval: float = 0.02) -> None:
    """
    Polls `predicate()` until it's truthy or `timeout` elapses. Pub/sub delivery over
    real Redis is asynchronous — a fixed `asyncio.sleep(0.3)` is exactly the kind of
    thing that's fine on a quiet machine and flaky the moment anything else (a second
    test, a loaded CI runner) is competing for the CPU. Polling with a generous
    timeout is fast on the happy path and robust under load.
    """
    elapsed = 0.0
    while elapsed < timeout:
        if predicate():
            return
        await asyncio.sleep(interval)
        elapsed += interval
    raise AssertionError(f"Condition not met within {timeout}s")


def test_second_process_sees_peer_registered_by_first_process():
    async def scenario(make_manager):
        process_a = make_manager()
        process_b = make_manager()

        await process_a.join("test-room-1", "peer-a", FakeSocket("a"))
        existing = await process_b.join("test-room-1", "peer-b", FakeSocket("b"))

        assert existing == [{"peer_id": "peer-a", "name": None}]

    _run(scenario)


def test_broadcast_from_process_a_reaches_peer_on_process_b():
    async def scenario(make_manager):
        process_a = make_manager()
        process_b = make_manager()

        socket_a = FakeSocket("a")
        await process_a.join("test-room-2", "peer-a", socket_a)
        socket_b = FakeSocket("b")
        await process_b.join("test-room-2", "peer-b", socket_b)

        await process_a.broadcast("test-room-2", {"type": "peer-joined", "peer_id": "peer-a"}, exclude="peer-a")
        await _wait_until(lambda: len(socket_b.received) > 0)

        assert socket_b.received == [{"type": "peer-joined", "peer_id": "peer-a"}]
        assert socket_a.received == []  # excluded — must not receive its own broadcast

    _run(scenario)


def test_targeted_send_to_only_reaches_the_right_peer_cross_process():
    async def scenario(make_manager):
        process_a = make_manager()
        process_b = make_manager()

        socket_b1 = FakeSocket("b1")
        socket_b2 = FakeSocket("b2")
        await process_b.join("test-room-3", "peer-b1", socket_b1)
        await process_b.join("test-room-3", "peer-b2", socket_b2)

        found = await process_a.send_to("test-room-3", "peer-b1", {"type": "signal", "data": "hello"})
        await _wait_until(lambda: len(socket_b1.received) > 0)

        assert found is True
        assert socket_b1.received == [{"type": "signal", "data": "hello"}]
        assert socket_b2.received == []  # not the target — must not receive it

    _run(scenario)


def test_send_to_unknown_peer_returns_false():
    async def scenario(make_manager):
        process_a = make_manager()
        found = await process_a.send_to("test-room-4", "nobody-here", {"type": "signal"})
        assert found is False

    _run(scenario)


def test_leave_removes_peer_from_shared_membership():
    async def scenario(make_manager):
        process_a = make_manager()
        process_b = make_manager()

        await process_a.join("test-room-5", "peer-a", FakeSocket())
        await process_a.leave("test-room-5", "peer-a")

        existing = await process_b.join("test-room-5", "peer-b", FakeSocket())
        assert existing == []  # peer-a's departure is visible to process_b

    _run(scenario)


def test_set_name_is_visible_across_processes():
    async def scenario(make_manager):
        process_a = make_manager()
        process_b = make_manager()

        await process_a.join("test-room-6", "peer-a", FakeSocket())
        await process_a.set_name("test-room-6", "peer-a", "Isabel")

        existing = await process_b.join("test-room-6", "peer-b", FakeSocket())
        assert existing == [{"peer_id": "peer-a", "name": "Isabel"}]

    _run(scenario)
