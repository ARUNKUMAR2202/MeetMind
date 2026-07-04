"""
Runs against an isolated SQLite file and the mock pipeline (USE_MOCK_PIPELINE=true is
the default), so this exercises the *entire* upload -> background job -> results flow
without needing OpenAI/Pinecone keys. This is the test to run first when something
"doesn't work" — if this passes, the wiring is fine and the bug is API-key/network related.
"""
import io
import os
import sys
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///./test_meetmind.db"
os.environ["USE_MOCK_PIPELINE"] = "true"
os.environ["REDIS_URL"] = ""

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


@pytest.fixture
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)


def _register_and_login(client, account_type="professional"):
    resp = client.post("/auth/register", json={
        "email": f"{account_type}@example.com",
        "password": "hunter22",
        "full_name": "Test User",
        "account_type": account_type,
    })
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["mock_pipeline"] is True


def test_register_duplicate_email_rejected(client):
    _register_and_login(client)
    resp = client.post("/auth/register", json={
        "email": "professional@example.com", "password": "x", "full_name": "Y",
    })
    assert resp.status_code == 400


def test_login_wrong_password_rejected(client):
    _register_and_login(client)
    resp = client.post("/auth/login", json={
        "email": "professional@example.com", "password": "wrong",
    })
    assert resp.status_code == 401


def test_upload_session_runs_mock_pipeline_end_to_end(client):
    headers = _register_and_login(client, account_type="professional")
    fake_audio = io.BytesIO(b"not-real-audio-bytes")

    resp = client.post(
        "/sessions",
        headers=headers,
        data={"title": "Monday Standup", "session_type": "professional"},
        files={"audio": ("standup.webm", fake_audio, "audio/webm")},
    )
    assert resp.status_code == 201, resp.text
    session = resp.json()
    assert session["status"] in ("uploaded", "processing", "completed")
    session_id = session["id"]

    # TestClient runs BackgroundTasks synchronously before returning, so it should
    # already be completed by the time we check.
    resp = client.get(f"/sessions/{session_id}", headers=headers)
    assert resp.status_code == 200
    result = resp.json()
    assert result["status"] == "completed"
    assert result["professional_output"] is not None
    assert len(result["professional_output"]["action_items"]) > 0
    assert result["professional_output"]["action_items"][0]["owner"]


def test_student_session_returns_quiz(client):
    headers = _register_and_login(client, account_type="student")
    fake_audio = io.BytesIO(b"not-real-audio-bytes")

    resp = client.post(
        "/sessions",
        headers=headers,
        data={"title": "Lecture 3", "session_type": "student"},
        files={"audio": ("lecture.webm", fake_audio, "audio/webm")},
    )
    session_id = resp.json()["id"]

    resp = client.get(f"/sessions/{session_id}", headers=headers)
    result = resp.json()
    assert result["status"] == "completed"
    assert len(result["student_output"]["quiz"]) > 0
    assert result["student_output"]["quiz"][0]["bloom_level"] in (
        "remembering", "understanding", "applying",
    )


def test_cannot_access_another_users_session(client):
    headers_a = _register_and_login(client, account_type="professional")
    fake_audio = io.BytesIO(b"bytes")
    resp = client.post(
        "/sessions", headers=headers_a,
        data={"title": "Private meeting", "session_type": "professional"},
        files={"audio": ("m.webm", fake_audio, "audio/webm")},
    )
    session_id = resp.json()["id"]

    headers_b = _register_and_login(client, account_type="student")
    resp = client.get(f"/sessions/{session_id}", headers=headers_b)
    assert resp.status_code == 404


def test_document_upload_for_rag_mock_mode(client):
    headers = _register_and_login(client, account_type="professional")
    fake_audio = io.BytesIO(b"bytes")
    resp = client.post(
        "/sessions", headers=headers,
        data={"title": "Planning", "session_type": "professional"},
        files={"audio": ("m.webm", fake_audio, "audio/webm")},
    )
    session_id = resp.json()["id"]

    resp = client.post(
        f"/sessions/{session_id}/documents", headers=headers,
        json={"title": "Q3 roadmap.pdf", "text": "This is the Q3 roadmap content." * 50},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["chunk_count"] >= 1


def test_document_upload_rejected_for_student_sessions(client):
    headers = _register_and_login(client, account_type="student")
    fake_audio = io.BytesIO(b"bytes")
    resp = client.post(
        "/sessions", headers=headers,
        data={"title": "Lecture", "session_type": "student"},
        files={"audio": ("m.webm", fake_audio, "audio/webm")},
    )
    session_id = resp.json()["id"]

    resp = client.post(
        f"/sessions/{session_id}/documents", headers=headers,
        json={"title": "Notes.pdf", "text": "Some notes."},
    )
    assert resp.status_code == 400
    assert "professional-team feature" in resp.json()["detail"]


def test_login_sets_httponly_cookie(client):
    _register_and_login(client, account_type="professional")
    resp = client.post("/auth/login", json={
        "email": "professional@example.com", "password": "hunter22",
    })
    assert resp.status_code == 200
    cookie = resp.cookies.get("meetmind_token")
    assert cookie is not None


def test_me_works_via_cookie_without_bearer_header(client):
    _register_and_login(client, account_type="professional")
    login_resp = client.post("/auth/login", json={
        "email": "professional@example.com", "password": "hunter22",
    })
    # No Authorization header at all — rely purely on the cookie the client now holds.
    resp = client.get("/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "professional@example.com"


def test_logout_clears_cookie(client):
    _register_and_login(client, account_type="professional")
    client.post("/auth/login", json={"email": "professional@example.com", "password": "hunter22"})
    resp = client.post("/auth/logout")
    assert resp.status_code == 204

    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_oversized_upload_rejected(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "max_upload_size_mb", 1)  # 1MB limit for this test

    headers = _register_and_login(client, account_type="professional")
    too_big = io.BytesIO(b"x" * (2 * 1024 * 1024))  # 2MB, over the limit
    resp = client.post(
        "/sessions", headers=headers,
        data={"title": "Too big", "session_type": "professional"},
        files={"audio": ("m.webm", too_big, "audio/webm")},
    )
    assert resp.status_code == 413


def test_download_audio_endpoint(client):
    headers = _register_and_login(client, account_type="professional")
    fake_audio = io.BytesIO(b"real-ish-audio-bytes")
    resp = client.post(
        "/sessions", headers=headers,
        data={"title": "Playback test", "session_type": "professional"},
        files={"audio": ("m.webm", fake_audio, "audio/webm")},
    )
    session_id = resp.json()["id"]

    resp = client.get(f"/sessions/{session_id}/audio", headers=headers)
    assert resp.status_code == 200
    assert resp.content == b"real-ish-audio-bytes"


def test_rate_limit_actually_blocks_when_enabled(client):
    """
    Rate limiting is disabled for the rest of this suite (see conftest.py) because
    slowapi's storage persists counts across the whole test run, and dozens of tests
    calling /auth/register would otherwise trip a real per-IP limit. This test flips
    it on just for itself to prove the decorator wiring genuinely works, then flips it
    back off so it doesn't affect any test that runs after it.
    """
    from app.rate_limit import limiter

    limiter.reset()
    limiter.enabled = True
    try:
        # /auth/register is limited to 5/minute (see routers/auth.py)
        last_status = None
        for i in range(7):
            resp = client.post("/auth/register", json={
                "email": f"ratelimit{i}@example.com", "password": "hunter22", "full_name": "X",
            })
            last_status = resp.status_code
        assert last_status == 429
    finally:
        limiter.enabled = False
        limiter.reset()


def test_delete_session_removes_it(client):
    headers = _register_and_login(client, account_type="professional")
    fake_audio = io.BytesIO(b"bytes")
    resp = client.post(
        "/sessions", headers=headers,
        data={"title": "Throwaway", "session_type": "professional"},
        files={"audio": ("m.webm", fake_audio, "audio/webm")},
    )
    session_id = resp.json()["id"]

    resp = client.delete(f"/sessions/{session_id}", headers=headers)
    assert resp.status_code == 204

    resp = client.get(f"/sessions/{session_id}", headers=headers)
    assert resp.status_code == 404


def test_delete_session_requires_ownership(client):
    headers_a = _register_and_login(client, account_type="professional")
    fake_audio = io.BytesIO(b"bytes")
    resp = client.post(
        "/sessions", headers=headers_a,
        data={"title": "Private", "session_type": "professional"},
        files={"audio": ("m.webm", fake_audio, "audio/webm")},
    )
    session_id = resp.json()["id"]

    headers_b = _register_and_login(client, account_type="student")
    resp = client.delete(f"/sessions/{session_id}", headers=headers_b)
    assert resp.status_code == 404

    # confirm it's still there for the real owner
    resp = client.get(f"/sessions/{session_id}", headers=headers_a)
    assert resp.status_code == 200


def test_live_session_creation_and_audio_attach(client):
    headers = _register_and_login(client, account_type="professional")

    resp = client.post(
        "/sessions/live", headers=headers,
        json={"title": "Live standup", "session_type": "professional"},
    )
    assert resp.status_code == 201, resp.text
    session = resp.json()
    assert session["status"] == "live"
    session_id = session["id"]

    # Simulates the room page uploading the recorded mix once the call ends.
    fake_recording = io.BytesIO(b"recorded-mixed-audio-bytes")
    resp = client.post(
        f"/sessions/{session_id}/audio", headers=headers,
        files={"audio": ("meeting.webm", fake_recording, "audio/webm")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "uploaded"  # background task hasn't run yet at serialization time

    # TestClient runs BackgroundTasks synchronously before returning, so a follow-up
    # GET reflects the completed state.
    resp = client.get(f"/sessions/{session_id}", headers=headers)
    result = resp.json()
    assert result["status"] == "completed"
    assert result["professional_output"] is not None


def test_attach_audio_rejects_empty_recording(client):
    headers = _register_and_login(client, account_type="professional")
    resp = client.post(
        "/sessions/live", headers=headers,
        json={"title": "Empty call", "session_type": "professional"},
    )
    session_id = resp.json()["id"]

    resp = client.post(
        f"/sessions/{session_id}/audio", headers=headers,
        files={"audio": ("meeting.webm", io.BytesIO(b""), "audio/webm")},
    )
    assert resp.status_code == 400
