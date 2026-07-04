"""
Signaling protocol (JSON messages over one WebSocket per participant):

Server -> client, on connect:
    {"type": "welcome", "peer_id": "<you>", "peers": [{"peer_id": "...", "name": null}, ...]}
Server -> existing peers, when someone joins:
    {"type": "peer-joined", "peer_id": "..."}
Client -> server, once the user enters a display name:
    {"type": "hello", "name": "Isabel"}
Server -> other peers, relaying that name:
    {"type": "peer-name", "peer_id": "...", "name": "Isabel"}
Client -> server, WebRTC handshake (SDP offer/answer or ICE candidate), targeted at
one peer:
    {"type": "signal", "to": "<peer_id>", "data": {"kind": "offer"|"answer"|"ice-candidate", ...}}
Server -> target peer, relayed:
    {"type": "signal", "from": "<sender_peer_id>", "data": {...}}
Server -> remaining peers, on disconnect:
    {"type": "peer-left", "peer_id": "..."}

The join convention (to avoid double-offers in mesh topology): a NEW peer creates an
offer to each peer already in the room (from the `peers` list in "welcome"). Existing
peers only ever respond with answers to offers they receive — they don't initiate.
"""
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services.room_manager import manager

router = APIRouter(tags=["rooms"])


@router.websocket("/ws/rooms/{room_id}")
async def room_signaling(websocket: WebSocket, room_id: str):
    await websocket.accept()
    peer_id = uuid.uuid4().hex[:8]
    existing_peers = await manager.join(room_id, peer_id, websocket)

    await websocket.send_json({"type": "welcome", "peer_id": peer_id, "peers": existing_peers})
    await manager.broadcast(room_id, {"type": "peer-joined", "peer_id": peer_id}, exclude=peer_id)

    try:
        while True:
            message = await websocket.receive_json()
            msg_type = message.get("type")

            if msg_type == "hello":
                name = str(message.get("name", ""))[:80]
                await manager.set_name(room_id, peer_id, name)
                await manager.broadcast(
                    room_id, {"type": "peer-name", "peer_id": peer_id, "name": name}, exclude=peer_id,
                )
            elif msg_type == "signal":
                target = message.get("to")
                if target:
                    await manager.send_to(
                        room_id, target, {"type": "signal", "from": peer_id, "data": message.get("data")},
                    )
            # Unknown message types are ignored rather than closing the connection —
            # keeps the protocol easy to extend (e.g. a future "chat" message type)
            # without breaking older clients.

    except WebSocketDisconnect:
        pass
    finally:
        await manager.leave(room_id, peer_id)
        await manager.broadcast(room_id, {"type": "peer-left", "peer_id": peer_id})
