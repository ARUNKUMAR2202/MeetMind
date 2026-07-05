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
Client -> server, host only, ends the meeting for everyone:
    {"type": "end-room"}
Server -> every peer (including the sender), once a host sends "end-room":
    {"type": "room-ended"}

The join convention (to avoid double-offers in mesh topology): a NEW peer creates an
offer to each peer already in the room (from the `peers` list in "welcome"). Existing
peers only ever respond with answers to offers they receive — they don't initiate.

Connect with `?user_id=<guest-id>&name=<display-name>` — user_id is a client-generated
id (see frontend/app/lib/guest.ts), persisted per participants row so the room's
history survives reconnects. There's no login in Phase 1, so this is NOT an auth
check; anyone who knows a room's id/code can join, same as an unlisted Zoom link.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session as DBSession

from ..database import SessionLocal, get_db
from ..models import Participant, Room
from ..schemas import RoomCreate, RoomEndIn, RoomOut
from ..services.room_manager import manager
from ..services.rooms import generate_room_code

router = APIRouter(tags=["rooms"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


@router.post("/rooms", response_model=RoomOut, status_code=201)
def create_room(payload: RoomCreate, db: DBSession = Depends(get_db)):
    room = Room(code=generate_room_code(db), host_id=payload.host_id, status="live")
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


@router.get("/rooms/by-code/{code}", response_model=RoomOut)
def get_room_by_code(code: str, db: DBSession = Depends(get_db)):
    room = db.query(Room).filter(Room.code == code.upper()).first()
    if room is None:
        raise HTTPException(status_code=404, detail="No room found for that code.")
    return room


@router.post("/rooms/{room_id}/end", response_model=RoomOut)
def end_room(room_id: str, payload: RoomEndIn, db: DBSession = Depends(get_db)):
    room = db.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found.")
    if room.host_id != payload.user_id:
        raise HTTPException(status_code=403, detail="Only the host can end this meeting.")
    room.status = "ended"
    room.ended_at = _now()
    db.commit()
    db.refresh(room)
    return room


@router.websocket("/ws/rooms/{room_id}")
async def room_signaling(websocket: WebSocket, room_id: str, user_id: str = Query(...), name: str = Query("")):
    db = SessionLocal()
    try:
        room = db.get(Room, room_id)
        if room is None:
            await websocket.close(code=4404)
            return
        if room.status == "ended":
            await websocket.close(code=4410)
            return

        await websocket.accept()
        peer_id = uuid.uuid4().hex[:8]

        participant = Participant(room_id=room_id, user_id=user_id, display_name=name or "Guest")
        db.add(participant)
        db.commit()
        db.refresh(participant)

        existing_peers = await manager.join(room_id, peer_id, websocket)
        if name:
            await manager.set_name(room_id, peer_id, name)

        await websocket.send_json({"type": "welcome", "peer_id": peer_id, "peers": existing_peers})
        await manager.broadcast(room_id, {"type": "peer-joined", "peer_id": peer_id}, exclude=peer_id)
        if name:
            await manager.broadcast(
                room_id, {"type": "peer-name", "peer_id": peer_id, "name": name}, exclude=peer_id,
            )

        try:
            while True:
                message = await websocket.receive_json()
                msg_type = message.get("type")

                if msg_type == "hello":
                    hello_name = str(message.get("name", ""))[:80]
                    await manager.set_name(room_id, peer_id, hello_name)
                    participant.display_name = hello_name or participant.display_name
                    db.commit()
                    await manager.broadcast(
                        room_id, {"type": "peer-name", "peer_id": peer_id, "name": hello_name}, exclude=peer_id,
                    )
                elif msg_type == "signal":
                    target = message.get("to")
                    if target:
                        await manager.send_to(
                            room_id, target, {"type": "signal", "from": peer_id, "data": message.get("data")},
                        )
                elif msg_type == "end-room":
                    db.refresh(room)
                    if user_id == room.host_id:
                        room.status = "ended"
                        room.ended_at = _now()
                        db.commit()
                        await manager.broadcast(room_id, {"type": "room-ended"})
                # Unknown message types are ignored rather than closing the connection —
                # keeps the protocol easy to extend (e.g. a future "chat" message type)
                # without breaking older clients.

        except WebSocketDisconnect:
            pass
        finally:
            participant.left_at = _now()
            db.commit()
            await manager.leave(room_id, peer_id)
            await manager.broadcast(room_id, {"type": "peer-left", "peer_id": peer_id})
    finally:
        db.close()
