"""
WebRTC signaling relay — this server never sees audio/video, only the small JSON
handshake messages peers use to find each other (SDP offers/answers, ICE candidates).

Two implementations behind the same async interface, chosen automatically based on
settings.redis_url (same pattern as services/pubsub.py):

- InMemoryRoomManager: everything lives in a local dict. Works great for one process,
  but two people in the same room MUST connect to the same backend instance.
- RedisRoomManager: room membership (who's in the room, their display names) lives in
  a Redis hash so ANY backend process can answer "who else is here" correctly. Message
  delivery (broadcasts and targeted signals) goes through a Redis pub/sub channel per
  room; each process filters incoming messages against its own LOCAL socket registry
  and only forwards to sockets it actually holds. This is what makes it work
  cross-process: a message published by process A reaches process B's subscriber,
  and process B delivers it to a locally-connected peer if the target is local to B.

Both are unit-tested directly — see backend/tests/test_rooms.py (protocol behavior,
in-memory) and backend/tests/test_room_manager_redis.py (real Redis, two independent
manager instances standing in for two backend processes).
"""
from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Optional, Protocol

from ..config import settings


class _SendableSocket(Protocol):
    async def send_json(self, data: dict) -> None: ...


class InMemoryRoomManager:
    def __init__(self) -> None:
        # room_id -> peer_id -> {"ws": socket, "name": str | None}
        self._rooms: dict[str, dict[str, dict]] = {}

    def _peers_in(self, room_id: str, exclude: Optional[str] = None) -> list[dict]:
        room = self._rooms.get(room_id, {})
        return [{"peer_id": pid, "name": info["name"]} for pid, info in room.items() if pid != exclude]

    async def join(self, room_id: str, peer_id: str, socket: _SendableSocket) -> list[dict]:
        room = self._rooms.setdefault(room_id, {})
        existing = self._peers_in(room_id)
        room[peer_id] = {"ws": socket, "name": None}
        return existing

    async def leave(self, room_id: str, peer_id: str) -> None:
        room = self._rooms.get(room_id)
        if not room:
            return
        room.pop(peer_id, None)
        if not room:
            self._rooms.pop(room_id, None)

    async def set_name(self, room_id: str, peer_id: str, name: str) -> None:
        room = self._rooms.get(room_id, {})
        if peer_id in room:
            room[peer_id]["name"] = name

    async def broadcast(self, room_id: str, message: dict, exclude: Optional[str] = None) -> None:
        room = self._rooms.get(room_id, {})
        for pid, info in list(room.items()):
            if pid == exclude:
                continue
            try:
                await info["ws"].send_json(message)
            except Exception:
                await self.leave(room_id, pid)

    async def send_to(self, room_id: str, peer_id: str, message: dict) -> bool:
        room = self._rooms.get(room_id, {})
        target = room.get(peer_id)
        if not target:
            return False
        try:
            await target["ws"].send_json(message)
            return True
        except Exception:
            await self.leave(room_id, peer_id)
            return False


class RedisRoomManager:
    """
    Cross-process room manager. See module docstring for the design.

    Uses its own dedicated Redis connection for pub/sub (not services/pubsub.py's
    module-level backend selection) so it's genuinely self-contained: two
    RedisRoomManager instances always talk through real Redis regardless of which
    pubsub backend the rest of the app happened to select at import time. That's also
    what makes it directly testable as "two backend processes" in a single test
    process — see tests/test_room_manager_redis.py.
    """

    def __init__(self, redis_url: Optional[str] = None) -> None:
        import redis.asyncio as aioredis
        self._redis = aioredis.from_url(redis_url or settings.redis_url, decode_responses=True)
        # Local-to-this-process socket registry, purely for delivery filtering.
        self._local_sockets: dict[str, dict[str, _SendableSocket]] = defaultdict(dict)
        self._listener_tasks: dict[str, asyncio.Task] = {}

    def _peers_key(self, room_id: str) -> str:
        return f"room-peers:{room_id}"

    def _channel(self, room_id: str) -> str:
        return f"room-signal:{room_id}"

    async def _publish(self, room_id: str, envelope: dict) -> None:
        await self._redis.publish(self._channel(room_id), json.dumps(envelope))

    async def _ensure_listener(self, room_id: str) -> None:
        if room_id in self._listener_tasks:
            return

        # Subscribe SYNCHRONOUSLY here (before returning to the caller) so that by the
        # time join() completes, this process is guaranteed to actually receive
        # anything published from this point on. Only the message-consuming loop runs
        # as a background task — the subscribe() call itself must be awaited inline,
        # or there's a window where a concurrent broadcast could fire before the
        # SUBSCRIBE command has actually reached Redis, and pub/sub messages are
        # fire-and-forget (no delivery to a not-yet-subscribed client).
        local_pubsub = self._redis.pubsub()
        await local_pubsub.subscribe(self._channel(room_id))

        async def _listen() -> None:
            try:
                async for message in local_pubsub.listen():
                    if message["type"] == "message":
                        await self._deliver_local(room_id, json.loads(message["data"]))
            finally:
                await local_pubsub.unsubscribe(self._channel(room_id))
                await local_pubsub.aclose()

        self._listener_tasks[room_id] = asyncio.create_task(_listen())

    async def _deliver_local(self, room_id: str, envelope: dict) -> None:
        sockets = self._local_sockets.get(room_id, {})
        target = envelope.get("target")
        payload = envelope["payload"]

        if target:
            ws = sockets.get(target)
            if ws:
                try:
                    await ws.send_json(payload)
                except Exception:
                    pass
            return

        exclude = envelope.get("exclude")
        for pid, ws in list(sockets.items()):
            if pid == exclude:
                continue
            try:
                await ws.send_json(payload)
            except Exception:
                pass

    async def join(self, room_id: str, peer_id: str, socket: _SendableSocket) -> list[dict]:
        # Subscribe BEFORE reading/writing membership so we can't miss a message
        # published by a concurrent joiner between our hgetall and our hset.
        await self._ensure_listener(room_id)
        existing_raw = await self._redis.hgetall(self._peers_key(room_id))
        existing = [
            {"peer_id": pid, "name": (name or None)}
            for pid, name in existing_raw.items() if pid != peer_id
        ]
        await self._redis.hset(self._peers_key(room_id), peer_id, "")
        self._local_sockets[room_id][peer_id] = socket
        return existing

    async def leave(self, room_id: str, peer_id: str) -> None:
        await self._redis.hdel(self._peers_key(room_id), peer_id)
        self._local_sockets.get(room_id, {}).pop(peer_id, None)
        if not self._local_sockets.get(room_id):
            task = self._listener_tasks.pop(room_id, None)
            if task:
                task.cancel()

    async def set_name(self, room_id: str, peer_id: str, name: str) -> None:
        await self._redis.hset(self._peers_key(room_id), peer_id, name)

    async def broadcast(self, room_id: str, message: dict, exclude: Optional[str] = None) -> None:
        await self._publish(room_id, {"payload": message, "exclude": exclude})

    async def send_to(self, room_id: str, peer_id: str, message: dict) -> bool:
        exists = await self._redis.hexists(self._peers_key(room_id), peer_id)
        if not exists:
            return False
        await self._publish(room_id, {"payload": message, "target": peer_id})
        return True

    async def close(self) -> None:
        """Cancels any listener tasks and closes the Redis connection. Mainly useful
        for tests that create short-lived manager instances — the app-level singleton
        below lives for the process lifetime and doesn't need this."""
        for task in self._listener_tasks.values():
            task.cancel()
        await self._redis.aclose()


manager = RedisRoomManager() if settings.redis_url else InMemoryRoomManager()
