"""
Session-status notifications ("processing" -> "completed"/"failed"), built on
services/pubsub.py. See that module's docstring for the Redis-vs-in-memory choice.
"""
from typing import AsyncIterator

from . import pubsub


def _channel(session_id: str) -> str:
    return f"session-status:{session_id}"


def broadcast_sync(session_id: str, message: dict) -> None:
    """Called from run_pipeline_job, which runs in a worker thread (FastAPI
    BackgroundTasks) with no running event loop — hence the sync publish."""
    pubsub.publish_sync(_channel(session_id), message)


async def stream_updates(session_id: str) -> AsyncIterator[dict]:
    async for message in pubsub.subscribe(_channel(session_id)):
        yield message
