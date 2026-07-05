"""
Tests the room REST endpoints and the signaling PROTOCOL end to end over real
(in-process) WebSocket connections — this is everything the server does; actual
media never touches the server so there's nothing else to test here without a real
browser.

Deliberately always exercises InMemoryRoomManager (see the REDIS_URL override below),
regardless of any ambient REDIS_URL in the environment — this file is testing the
signaling PROTOCOL itself, which is identical either way, and doing so against
in-memory avoids the extra async hop of a real Redis round-trip so timing stays snappy
and deterministic. The Redis-backed manager has its own dedicated real-Redis test file:
test_room_manager_redis.py.
"""
import os
import sys
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///./test_rooms.db"
os.environ["USE_MOCK_PIPELINE"] = "true"
os.environ["REDIS_URL"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models import Participant, Room


@pytest.fixture
def client():
    # Using the context-manager form matters here, not just style: it's what makes
    # Starlette's TestClient run the app's lifespan (so pubsub.bind_main_loop() and
    # init_db() actually execute) AND reuse a single blocking portal/thread for every
    # websocket_connect() call in this test. Without it, each websocket_connect()
    # spins up its OWN portal thread, and multiple "peers" in one test end up
    # mutating RoomManager's shared dict from different OS threads with no
    # synchronization — a real, if test-only, race condition (it showed up as
    # intermittent hangs in the 3-peer signaling test before this fix).
    with TestClient(app) as c:
        yield c


def _create_room(client, host_id="host-1", display_name="Host"):
    res = client.post("/rooms", json={"host_id": host_id, "display_name": display_name})
    assert res.status_code == 201
    return res.json()


def _ws_url(room_id: str, user_id: str, name: str = "") -> str:
    return f"/ws/rooms/{room_id}?user_id={user_id}&name={name}"


def test_create_room_returns_a_shareable_code(client):
    room = _create_room(client)
    assert room["status"] == "live"
    assert len(room["code"]) == 6
    assert room["host_id"] == "host-1"


def test_get_room_by_code_is_case_insensitive(client):
    room = _create_room(client)
    res = client.get(f"/rooms/by-code/{room['code'].lower()}")
    assert res.status_code == 200
    assert res.json()["id"] == room["id"]


def test_get_room_by_code_404_for_unknown_code(client):
    res = client.get("/rooms/by-code/ZZZZZZ")
    assert res.status_code == 404


def test_only_host_can_end_room(client):
    room = _create_room(client, host_id="host-1")
    res = client.post(f"/rooms/{room['id']}/end", json={"user_id": "someone-else"})
    assert res.status_code == 403

    res = client.post(f"/rooms/{room['id']}/end", json={"user_id": "host-1"})
    assert res.status_code == 200
    assert res.json()["status"] == "ended"


def test_single_peer_gets_welcome_with_empty_peer_list(client):
    room = _create_room(client)
    with client.websocket_connect(_ws_url(room["id"], "host-1", "Host")) as ws:
        msg = ws.receive_json()
        assert msg["type"] == "welcome"
        assert msg["peers"] == []
        assert len(msg["peer_id"]) > 0


def test_second_peer_sees_first_in_welcome_and_first_is_notified(client):
    room = _create_room(client)
    with client.websocket_connect(_ws_url(room["id"], "host-1", "Host")) as ws1:
        welcome1 = ws1.receive_json()
        peer1_id = welcome1["peer_id"]

        with client.websocket_connect(_ws_url(room["id"], "guest-2", "Guest")) as ws2:
            welcome2 = ws2.receive_json()
            assert welcome2["peers"] == [{"peer_id": peer1_id, "name": "Host"}]

            joined_event = ws1.receive_json()
            assert joined_event["type"] == "peer-joined"
            assert joined_event["peer_id"] == welcome2["peer_id"]

            name_event = ws1.receive_json()
            assert name_event == {"type": "peer-name", "peer_id": welcome2["peer_id"], "name": "Guest"}


def test_hello_broadcasts_name_to_other_peers_and_updates_participant_row(client):
    room = _create_room(client)
    with client.websocket_connect(_ws_url(room["id"], "host-1", "Host")) as ws1:
        ws1.receive_json()  # welcome
        with client.websocket_connect(_ws_url(room["id"], "guest-isabel")) as ws2:
            welcome2 = ws2.receive_json()
            ws1.receive_json()  # peer-joined for ws2

            ws2.send_json({"type": "hello", "name": "Isabel"})
            name_event = ws1.receive_json()
            assert name_event == {"type": "peer-name", "peer_id": welcome2["peer_id"], "name": "Isabel"}

    db = SessionLocal()
    try:
        participant = db.query(Participant).filter(Participant.user_id == "guest-isabel").one()
        assert participant.display_name == "Isabel"
        assert participant.left_at is not None
    finally:
        db.close()


def test_signal_relays_only_to_targeted_peer(client):
    room = _create_room(client)
    with client.websocket_connect(_ws_url(room["id"], "p1")) as ws1:
        welcome1 = ws1.receive_json()
        peer1 = welcome1["peer_id"]

        with client.websocket_connect(_ws_url(room["id"], "p2")) as ws2:
            welcome2 = ws2.receive_json()
            peer2 = welcome2["peer_id"]
            ws1.receive_json()  # peer-joined

            with client.websocket_connect(_ws_url(room["id"], "p3")) as ws3:
                ws3.receive_json()  # welcome
                ws1.receive_json()  # peer-joined for ws3
                ws2.receive_json()  # peer-joined for ws3

                # ws3 sends an offer targeted only at peer1 — peer2 must NOT receive it.
                offer = {"type": "signal", "to": peer1, "data": {"kind": "offer", "sdp": "fake-sdp"}}
                ws3.send_json(offer)

                received = ws1.receive_json()
                assert received["type"] == "signal"
                assert received["data"] == {"kind": "offer", "sdp": "fake-sdp"}

                # peer2 got nothing from this — send a targeted message TO peer2 now
                # and confirm peer1 doesn't see it, proving isolation both ways.
                ws3.send_json({"type": "signal", "to": peer2, "data": {"kind": "ping"}})
                received2 = ws2.receive_json()
                assert received2["data"] == {"kind": "ping"}


def test_peer_left_broadcast_on_disconnect(client):
    room = _create_room(client)
    with client.websocket_connect(_ws_url(room["id"], "p1")) as ws1:
        ws1.receive_json()  # welcome
        with client.websocket_connect(_ws_url(room["id"], "p2")) as ws2:
            welcome2 = ws2.receive_json()
            ws1.receive_json()  # peer-joined

        # ws2's `with` block just exited -> disconnected
        left_event = ws1.receive_json()
        assert left_event == {"type": "peer-left", "peer_id": welcome2["peer_id"]}


def test_rooms_are_isolated_from_each_other(client):
    room_a = _create_room(client, host_id="host-a")
    room_b = _create_room(client, host_id="host-b")
    with client.websocket_connect(_ws_url(room_a["id"], "host-a")) as ws_a:
        ws_a.receive_json()
        with client.websocket_connect(_ws_url(room_b["id"], "host-b")) as ws_b:
            welcome_b = ws_b.receive_json()
            assert welcome_b["peers"] == []  # room-a's peer must not leak into room-b


def test_connecting_to_unknown_room_is_rejected(client):
    with pytest.raises(Exception):
        with client.websocket_connect(_ws_url("00000000-0000-0000-0000-000000000000", "someone")) as ws:
            ws.receive_json()


def test_host_end_room_broadcasts_to_everyone_and_persists_status(client):
    room = _create_room(client, host_id="host-1")
    with client.websocket_connect(_ws_url(room["id"], "host-1", "Host")) as ws1:
        ws1.receive_json()  # welcome
        with client.websocket_connect(_ws_url(room["id"], "guest-2", "Guest")) as ws2:
            ws2.receive_json()  # welcome
            ws1.receive_json()  # peer-joined
            ws1.receive_json()  # peer-name

            ws1.send_json({"type": "end-room"})

            assert ws1.receive_json() == {"type": "room-ended"}
            assert ws2.receive_json() == {"type": "room-ended"}

    db = SessionLocal()
    try:
        assert db.get(Room, room["id"]).status == "ended"
    finally:
        db.close()


def test_non_host_cannot_end_room_over_websocket(client):
    room = _create_room(client, host_id="host-1")
    with client.websocket_connect(_ws_url(room["id"], "host-1")) as ws1:
        ws1.receive_json()  # welcome
        with client.websocket_connect(_ws_url(room["id"], "guest-2")) as ws2:
            ws2.receive_json()  # welcome
            ws1.receive_json()  # peer-joined

            ws2.send_json({"type": "end-room"})
            ws2.close()

    db = SessionLocal()
    try:
        assert db.get(Room, room["id"]).status == "live"
    finally:
        db.close()
