"""
Tests the signaling PROTOCOL end to end over real (in-process) WebSocket connections —
this is everything the server does; actual media never touches the server so there's
nothing else to test here without a real browser.

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


def test_single_peer_gets_welcome_with_empty_peer_list(client):
    with client.websocket_connect("/ws/rooms/room-1") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "welcome"
        assert msg["peers"] == []
        assert len(msg["peer_id"]) > 0


def test_second_peer_sees_first_in_welcome_and_first_is_notified(client):
    with client.websocket_connect("/ws/rooms/room-2") as ws1:
        welcome1 = ws1.receive_json()
        peer1_id = welcome1["peer_id"]

        with client.websocket_connect("/ws/rooms/room-2") as ws2:
            welcome2 = ws2.receive_json()
            assert welcome2["peers"] == [{"peer_id": peer1_id, "name": None}]

            joined_event = ws1.receive_json()
            assert joined_event["type"] == "peer-joined"
            assert joined_event["peer_id"] == welcome2["peer_id"]


def test_hello_broadcasts_name_to_other_peers(client):
    with client.websocket_connect("/ws/rooms/room-3") as ws1:
        ws1.receive_json()  # welcome
        with client.websocket_connect("/ws/rooms/room-3") as ws2:
            welcome2 = ws2.receive_json()
            ws1.receive_json()  # peer-joined for ws2

            ws2.send_json({"type": "hello", "name": "Isabel"})
            name_event = ws1.receive_json()
            assert name_event == {"type": "peer-name", "peer_id": welcome2["peer_id"], "name": "Isabel"}


def test_signal_relays_only_to_targeted_peer(client):
    with client.websocket_connect("/ws/rooms/room-4") as ws1:
        welcome1 = ws1.receive_json()
        peer1 = welcome1["peer_id"]

        with client.websocket_connect("/ws/rooms/room-4") as ws2:
            welcome2 = ws2.receive_json()
            peer2 = welcome2["peer_id"]
            ws1.receive_json()  # peer-joined

            with client.websocket_connect("/ws/rooms/room-4") as ws3:
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
    with client.websocket_connect("/ws/rooms/room-5") as ws1:
        ws1.receive_json()  # welcome
        with client.websocket_connect("/ws/rooms/room-5") as ws2:
            welcome2 = ws2.receive_json()
            ws1.receive_json()  # peer-joined

        # ws2's `with` block just exited -> disconnected
        left_event = ws1.receive_json()
        assert left_event == {"type": "peer-left", "peer_id": welcome2["peer_id"]}


def test_rooms_are_isolated_from_each_other(client):
    with client.websocket_connect("/ws/rooms/room-a") as ws_a:
        ws_a.receive_json()
        with client.websocket_connect("/ws/rooms/room-b") as ws_b:
            welcome_b = ws_b.receive_json()
            assert welcome_b["peers"] == []  # room-a's peer must not leak into room-b
