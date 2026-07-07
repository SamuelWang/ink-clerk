import time
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from google_auth_oauthlib.flow import Flow
from oauthlib.oauth2.rfc6749.errors import InvalidGrantError

from main import app
from routers import auth as auth_module

# NOTE for the routers/auth.py implementation (Task 6.3): read GOOGLE_CLIENT_ID and
# PUBLIC_BASE_URL via os.environ inside the endpoint handler (request time), not as
# module-level constants computed at import time -- these tests rely on monkeypatch.setenv
# taking effect per-test.


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _configure_oauth_env(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://inkclerk-auth.example.com")


def _patch_successful_token_exchange(
    monkeypatch,
    *,
    access_token="fake-access-token",
    refresh_token="fake-refresh-token",
    expires_in=3600,
) -> None:
    def _fake_fetch_token(self, **kwargs):
        self.oauth2session.token = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": time.time() + expires_in,
            "token_type": "Bearer",
            "scope": " ".join(auth_module.SCOPES),
        }
        return self.oauth2session.token

    monkeypatch.setattr(Flow, "fetch_token", _fake_fetch_token)


def _patch_rejected_token_exchange(monkeypatch) -> None:
    def _fake_fetch_token(self, **kwargs):
        raise InvalidGrantError(description="Bad Request")

    monkeypatch.setattr(Flow, "fetch_token", _fake_fetch_token)


client = TestClient(app, follow_redirects=False)


# ---------------------------------------------------------------------------
# TestAuthGoogleStart
# ---------------------------------------------------------------------------


class TestAuthGoogleStart:
    def test_returns_302_redirect(self, monkeypatch):
        _configure_oauth_env(monkeypatch)

        response = client.get(
            "/auth/google/start", params={"session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"}
        )

        assert response.status_code == 302

    def test_location_redirects_to_google_authorize_endpoint(self, monkeypatch):
        _configure_oauth_env(monkeypatch)

        response = client.get(
            "/auth/google/start", params={"session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"}
        )

        location = urlparse(response.headers["location"])
        assert location.hostname == "accounts.google.com"

    def test_redirect_includes_correct_client_id(self, monkeypatch):
        _configure_oauth_env(monkeypatch)

        response = client.get(
            "/auth/google/start", params={"session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"}
        )

        qs = parse_qs(urlparse(response.headers["location"]).query)
        assert qs["client_id"] == ["test-client-id.apps.googleusercontent.com"]

    def test_redirect_includes_correct_redirect_uri(self, monkeypatch):
        _configure_oauth_env(monkeypatch)

        response = client.get(
            "/auth/google/start", params={"session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"}
        )

        qs = parse_qs(urlparse(response.headers["location"]).query)
        assert qs["redirect_uri"] == ["https://inkclerk-auth.example.com/auth/google/callback"]

    def test_redirect_includes_both_readonly_scopes(self, monkeypatch):
        _configure_oauth_env(monkeypatch)

        response = client.get(
            "/auth/google/start", params={"session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"}
        )

        qs = parse_qs(urlparse(response.headers["location"]).query)
        scopes = qs["scope"][0].split()
        assert "https://www.googleapis.com/auth/documents.readonly" in scopes
        assert "https://www.googleapis.com/auth/drive.readonly" in scopes

    def test_state_equals_session_id(self, monkeypatch):
        _configure_oauth_env(monkeypatch)
        session_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"

        response = client.get("/auth/google/start", params={"session_id": session_id})

        qs = parse_qs(urlparse(response.headers["location"]).query)
        assert qs["state"] == [session_id]

    def test_redirect_requests_offline_access_and_consent_prompt(self, monkeypatch):
        _configure_oauth_env(monkeypatch)

        response = client.get(
            "/auth/google/start", params={"session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"}
        )

        qs = parse_qs(urlparse(response.headers["location"]).query)
        assert qs["access_type"] == ["offline"]
        assert qs["prompt"] == ["consent"]


# ---------------------------------------------------------------------------
# TestAuthGoogleCallback
# ---------------------------------------------------------------------------


class TestAuthGoogleCallback:
    @pytest.fixture(autouse=True)
    def _clear_session_store(self):
        auth_module._session_store.clear()
        yield
        auth_module._session_store.clear()

    def test_returns_200_html_success_page(self, monkeypatch):
        _configure_oauth_env(monkeypatch)
        _patch_successful_token_exchange(monkeypatch)

        response = client.get(
            "/auth/google/callback",
            params={"code": "auth-code-abc", "state": "session-123"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert "Authentication complete" in response.text

    def test_stores_ready_status_keyed_by_state(self, monkeypatch):
        _configure_oauth_env(monkeypatch)
        _patch_successful_token_exchange(monkeypatch)
        session_id = "session-123"

        client.get(
            "/auth/google/callback",
            params={"code": "auth-code-abc", "state": session_id},
        )

        assert auth_module._session_store[session_id]["status"] == "ready"

    def test_stores_correct_access_and_refresh_token(self, monkeypatch):
        _configure_oauth_env(monkeypatch)
        _patch_successful_token_exchange(
            monkeypatch, access_token="tok-abc", refresh_token="refresh-xyz"
        )
        session_id = "session-123"

        client.get(
            "/auth/google/callback",
            params={"code": "auth-code-abc", "state": session_id},
        )

        entry = auth_module._session_store[session_id]
        assert entry["access_token"] == "tok-abc"
        assert entry["refresh_token"] == "refresh-xyz"

    def test_stores_expires_in_close_to_configured_value(self, monkeypatch):
        _configure_oauth_env(monkeypatch)
        _patch_successful_token_exchange(monkeypatch, expires_in=3600)
        session_id = "session-123"

        client.get(
            "/auth/google/callback",
            params={"code": "auth-code-abc", "state": session_id},
        )

        expires_in = auth_module._session_store[session_id]["expires_in"]
        assert 3590 <= expires_in <= 3600

    def test_session_store_key_is_state_not_code(self, monkeypatch):
        _configure_oauth_env(monkeypatch)
        _patch_successful_token_exchange(monkeypatch)
        session_id = "the-state-value"

        client.get(
            "/auth/google/callback",
            params={"code": "a-totally-different-value", "state": session_id},
        )

        assert session_id in auth_module._session_store
        assert "a-totally-different-value" not in auth_module._session_store

    @pytest.mark.parametrize(
        "params",
        [
            {"state": "session-123"},
            {"code": "auth-code-abc"},
        ],
    )
    def test_missing_required_param_returns_error_page_without_crashing(
        self, monkeypatch, params
    ):
        _configure_oauth_env(monkeypatch)

        response = client.get("/auth/google/callback", params=params)

        assert 400 <= response.status_code < 500
        assert response.headers["content-type"].startswith("text/html")

    def test_invalid_code_returns_error_page_without_crashing(self, monkeypatch):
        _configure_oauth_env(monkeypatch)
        _patch_rejected_token_exchange(monkeypatch)
        session_id = "session-123"

        response = client.get(
            "/auth/google/callback",
            params={"code": "bad-code", "state": session_id},
        )

        assert 400 <= response.status_code < 500
        assert response.headers["content-type"].startswith("text/html")
        assert session_id not in auth_module._session_store


# ---------------------------------------------------------------------------
# TestAuthGoogleSession
# ---------------------------------------------------------------------------


class TestAuthGoogleSession:
    @pytest.fixture(autouse=True)
    def _clear_session_store(self):
        auth_module._session_store.clear()
        yield
        auth_module._session_store.clear()

    def test_unknown_session_id_returns_pending(self):
        response = client.get("/auth/google/session/never-seen-session-id")

        assert response.status_code == 200
        assert response.json() == {"status": "pending"}

    def test_ready_session_returns_stored_token_payload(self, monkeypatch):
        _configure_oauth_env(monkeypatch)
        _patch_successful_token_exchange(
            monkeypatch, access_token="tok-abc", refresh_token="refresh-xyz", expires_in=3600
        )
        session_id = "session-123"
        client.get(
            "/auth/google/callback",
            params={"code": "auth-code-abc", "state": session_id},
        )

        response = client.get(f"/auth/google/session/{session_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ready"
        assert body["access_token"] == "tok-abc"
        assert body["refresh_token"] == "refresh-xyz"
        assert 3590 <= body["expires_in"] <= 3600

    def test_second_call_after_claim_returns_expired(self, monkeypatch):
        _configure_oauth_env(monkeypatch)
        _patch_successful_token_exchange(monkeypatch)
        session_id = "session-123"
        client.get(
            "/auth/google/callback",
            params={"code": "auth-code-abc", "state": session_id},
        )

        first = client.get(f"/auth/google/session/{session_id}")
        second = client.get(f"/auth/google/session/{session_id}")

        assert first.json()["status"] == "ready"
        assert second.json() == {"status": "expired"}

    def test_session_past_ttl_never_claimed_returns_expired(self):
        session_id = "stale-session"
        auth_module._session_store[session_id] = {
            "status": "ready",
            "access_token": "fake-access-token",
            "refresh_token": "fake-refresh-token",
            "expires_in": 3600,
            "created_at": time.time() - auth_module.SESSION_TTL_SECONDS - 1,
        }

        response = client.get(f"/auth/google/session/{session_id}")

        assert response.status_code == 200
        assert response.json() == {"status": "expired"}
