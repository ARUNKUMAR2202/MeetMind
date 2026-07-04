"""
One pub/sub interface, two backends, selected automatically:

- REDIS_URL set -> real Redis pub/sub. Required once you run more than one backend
  process (Docker Compose already starts a `redis` service — set REDIS_URL to
  `redis://redis:6379/0` there to turn this on).
- REDIS_URL unset -> in-memory asyncio queues. Fine for a single dev/demo process,
  but two people in the same video-conference room (or two people watching the same
  session's status) MUST hit the same backend instance for this to work.

Both `pipeline_service.py` (session status) and `room_manager.py` (WebRTC signaling)
build on top of `subscribe`/`publish_sync` rather than talking to Redis directly, so
neither has to know which backend is active.

`publish_sync` exists because session-status updates are published from
`run_pipeline_job`, which FastAPI's BackgroundTasks runs in a worker thread with no
running asyncio event loop — it can't just `await` a publish.
"""
from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import AsyncIterator

from ..config import settings

_main_loop: asyncio.AbstractEventLoop | None = None


def bind_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Call once at app startup (see main.py's lifespan) — only used by the in-memory
    backend, so publish_sync can safely schedule work onto the loop from other threads."""
    global _main_loop
    _main_loop = loop


if settings.redis_url:
    import redis
    import redis.asyncio as aioredis

    _async_redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    _sync_redis = redis.from_url(settings.redis_url, decode_responses=True)
    BACKEND = "redis"

    async def subscribe(channel: str) -> AsyncIterator[dict]:
        pubsub = _async_redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield json.loads(message["data"])
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    def publish_sync(channel: str, data: dict) -> None:
        _sync_redis.publish(channel, json.dumps(data))

    async def publish(channel: str, data: dict) -> None:
        await _async_redis.publish(channel, json.dumps(data))

else:
    _subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)
    BACKEND = "memory"

    async def subscribe(channel: str) -> AsyncIterator[dict]:
        queue: asyncio.Queue = asyncio.Queue()
        _subscribers[channel].append(queue)
        try:
            while True:
                data = await queue.get()
                yield data
        finally:
            if queue in _subscribers[channel]:
                _subscribers[channel].remove(queue)

    def publish_sync(channel: str, data: dict) -> None:
        queues = list(_subscribers.get(channel, []))
        if not queues:
            return
        if _main_loop is None:
            # No loop registered (e.g. running outside the FastAPI app, like a script
            # or a test that never called bind_main_loop) — best effort, drop silently
            # rather than crash a background job over a status notification.
            return
        for queue in queues:
            _main_loop.call_soon_threadsafe(queue.put_nowait, data)

    async def publish(channel: str, data: dict) -> None:
        for queue in list(_subscribers.get(channel, [])):
            await queue.put(data)
