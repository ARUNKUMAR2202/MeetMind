import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services import ws_manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/sessions/{session_id}")
async def session_status_socket(websocket: WebSocket, session_id: str):
    """
    Frontend note: connect as soon as the upload response comes back with a session id.
    Messages look like: {"status": "processing"} -> {"status": "completed"} or
    {"status": "failed", "error": "..."}. On "completed", re-fetch GET /sessions/{id}
    for the full payload rather than trying to stream results over the socket itself.
    """
    await websocket.accept()

    async def forward_updates():
        async for message in ws_manager.stream_updates(session_id):
            await websocket.send_json(message)

    async def watch_for_disconnect():
        # We don't expect client messages, but this detects disconnects promptly.
        while True:
            await websocket.receive_text()

    forward_task = asyncio.create_task(forward_updates())
    watch_task = asyncio.create_task(watch_for_disconnect())

    try:
        done, pending = await asyncio.wait(
            {forward_task, watch_task}, return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        for task in done:
            exc = task.exception()
            if exc:
                raise exc
    except WebSocketDisconnect:
        pass
    finally:
        forward_task.cancel()
        watch_task.cancel()
