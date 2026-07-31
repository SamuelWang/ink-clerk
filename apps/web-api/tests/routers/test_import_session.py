import time

import pytest
from fastapi.testclient import TestClient

from main import app
from routers import import_session as import_session_module

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_session_store():
    import_session_module._session_store.clear()
    yield
    import_session_module._session_store.clear()


def _complete(session_id, **overrides):
    body = {
        "access_token": "tok-abc",
        "expires_in": 3600,
        "file_id": "doc-1",
        "file_name": "My Doc",
        **overrides,
    }
    return client.post(f"/import/google-doc/session/{session_id}/complete", json=body)


class TestGetSession:
    def test_unknown_session_id_returns_pending(self):
        response = client.get("/import/google-doc/session/never-seen-session-id")

        assert response.status_code == 200
        assert response.json() == {"status": "pending"}

    def test_ready_session_returns_stored_payload(self):
        session_id = "session-123"
        _complete(session_id, access_token="tok-abc", expires_in=3600, file_id="doc-1", file_name="My Doc")

        response = client.get(f"/import/google-doc/session/{session_id}")

        assert response.status_code == 200
        body = response.json()
        assert body == {
            "status": "ready",
            "access_token": "tok-abc",
            "expires_in": 3600,
            "file_id": "doc-1",
            "file_name": "My Doc",
            "resource_key": "",
        }

    def test_second_call_after_claim_returns_expired(self):
        session_id = "session-123"
        _complete(session_id)

        first = client.get(f"/import/google-doc/session/{session_id}")
        second = client.get(f"/import/google-doc/session/{session_id}")

        assert first.json()["status"] == "ready"
        assert second.json() == {"status": "expired"}

    def test_session_past_ttl_never_claimed_returns_expired(self):
        session_id = "stale-session"
        import_session_module._session_store[session_id] = {
            "status": "ready",
            "access_token": "tok-abc",
            "expires_in": 3600,
            "file_id": "doc-1",
            "file_name": "My Doc",
            "created_at": time.time() - import_session_module.SESSION_TTL_SECONDS - 1,
        }

        response = client.get(f"/import/google-doc/session/{session_id}")

        assert response.status_code == 200
        assert response.json() == {"status": "expired"}


class TestCompleteSession:
    def test_valid_complete_stores_ready_entry(self):
        session_id = "session-123"

        response = _complete(session_id, access_token="tok-abc", file_id="doc-1", file_name="My Doc")

        assert response.status_code == 200
        entry = import_session_module._session_store[session_id]
        assert entry["status"] == "ready"
        assert entry["access_token"] == "tok-abc"
        assert entry["file_id"] == "doc-1"
        assert entry["file_name"] == "My Doc"
        assert entry["resource_key"] == ""

    def test_resource_key_stored_and_returned(self):
        session_id = "session-123"

        _complete(session_id, resource_key="rk-1")
        response = client.get(f"/import/google-doc/session/{session_id}")

        assert response.json()["resource_key"] == "rk-1"
