from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from main import app

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
