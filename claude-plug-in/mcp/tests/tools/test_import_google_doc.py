import json

import httpx
import pytest
from googleapiclient.errors import HttpError

import tools.import_google_doc as import_google_doc
from shared.errors import AuthRequiredError, GoogleApiError, PermissionDeniedError
from tools.import_google_doc import export_doc_html, get_credentials, parse_doc_id


class TestParseDocId:
    def test_extracts_id_from_edit_url(self):
        url = "https://docs.google.com/document/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms/edit"
        assert parse_doc_id(url) == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms"

    def test_extracts_id_from_bare_url(self):
        url = "https://docs.google.com/document/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms/"
        assert parse_doc_id(url) == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms"

    def test_returns_bare_id_as_is(self):
        doc_id = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms"
        assert parse_doc_id(doc_id) == doc_id

    def test_raises_google_api_error_when_docs_google_com_url_unmatched(self):
        with pytest.raises(GoogleApiError):
            parse_doc_id("https://docs.google.com/spreadsheets/d/abc123/edit")


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict:
        return self._payload


@pytest.fixture(autouse=True)
def _isolated_token_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(import_google_doc, "TOKEN_CACHE_PATH", tmp_path / "google-token.json")
    monkeypatch.setenv("INKCLERK_AUTH_SERVICE_URL", "https://auth.example.com")
    monkeypatch.setattr(import_google_doc.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(import_google_doc.webbrowser, "open", lambda _url: True)


class TestGetCredentialsFirstRun:
    def test_no_cache_polls_until_ready_and_writes_cache(self, monkeypatch):
        opened_urls = []
        monkeypatch.setattr(
            import_google_doc.webbrowser, "open", lambda url: opened_urls.append(url)
        )

        responses = iter(
            [
                _FakeResponse({"status": "pending"}),
                _FakeResponse({"status": "pending"}),
                _FakeResponse(
                    {
                        "status": "ready",
                        "access_token": "at-1",
                        "refresh_token": "rt-1",
                        "expires_in": 3600,
                    }
                ),
            ]
        )
        monkeypatch.setattr(import_google_doc.httpx, "get", lambda _url: next(responses))

        creds = get_credentials()

        assert creds.token == "at-1"
        assert opened_urls[0].startswith("https://auth.example.com/auth/google/start?session_id=")
        cached = json.loads(import_google_doc.TOKEN_CACHE_PATH.read_text(encoding="utf-8"))
        assert cached["access_token"] == "at-1"
        assert cached["refresh_token"] == "rt-1"

    def test_expired_status_raises_auth_required(self, monkeypatch):
        monkeypatch.setattr(
            import_google_doc.httpx, "get", lambda _url: _FakeResponse({"status": "expired"})
        )

        with pytest.raises(AuthRequiredError):
            get_credentials()

    def test_timeout_without_ready_raises_auth_required(self, monkeypatch):
        monkeypatch.setattr(
            import_google_doc.httpx, "get", lambda _url: _FakeResponse({"status": "pending"})
        )

        with pytest.raises(AuthRequiredError):
            get_credentials()

    def test_request_error_during_poll_raises_auth_required(self, monkeypatch):
        def _raise(_url):
            raise httpx.RequestError("connection failed")

        monkeypatch.setattr(import_google_doc.httpx, "get", _raise)

        with pytest.raises(AuthRequiredError):
            get_credentials()

    def test_missing_auth_service_url_raises_auth_required_without_network_call(
        self, monkeypatch
    ):
        monkeypatch.delenv("INKCLERK_AUTH_SERVICE_URL", raising=False)

        def _fail(*_args, **_kwargs):
            raise AssertionError("should not make a network call")

        monkeypatch.setattr(import_google_doc.httpx, "get", _fail)
        monkeypatch.setattr(import_google_doc.httpx, "post", _fail)

        with pytest.raises(AuthRequiredError):
            get_credentials()


class TestGetCredentialsCached:
    def _write_cache(self, expiry_delta_seconds: float):
        expiry = import_google_doc._compute_expiry(expiry_delta_seconds)
        import_google_doc._write_cached_token(
            {"access_token": "cached-at", "refresh_token": "cached-rt", "expiry": expiry}
        )

    def test_unexpired_cache_builds_credentials_without_network_call(self, monkeypatch):
        self._write_cache(3600)

        def _fail(*_args, **_kwargs):
            raise AssertionError("should not make a network call")

        monkeypatch.setattr(import_google_doc.httpx, "get", _fail)
        monkeypatch.setattr(import_google_doc.httpx, "post", _fail)

        creds = get_credentials()
        assert creds.token == "cached-at"

    def test_expired_cache_refreshes_and_rewrites_cache(self, monkeypatch):
        self._write_cache(-10)

        posted = {}

        def _post(url, json):
            posted["url"] = url
            posted["json"] = json
            return _FakeResponse({"access_token": "new-at", "expires_in": 3600})

        monkeypatch.setattr(import_google_doc.httpx, "post", _post)

        creds = get_credentials()

        assert creds.token == "new-at"
        assert posted["url"] == "https://auth.example.com/auth/refresh"
        assert posted["json"] == {"refresh_token": "cached-rt"}
        cached = json.loads(import_google_doc.TOKEN_CACHE_PATH.read_text(encoding="utf-8"))
        assert cached["access_token"] == "new-at"
        assert cached["refresh_token"] == "cached-rt"

    def test_refresh_persists_rotated_refresh_token(self, monkeypatch):
        self._write_cache(-10)
        monkeypatch.setattr(
            import_google_doc.httpx,
            "post",
            lambda url, json: _FakeResponse(
                {"access_token": "new-at", "refresh_token": "rotated-rt", "expires_in": 3600}
            ),
        )

        get_credentials()

        cached = json.loads(import_google_doc.TOKEN_CACHE_PATH.read_text(encoding="utf-8"))
        assert cached["refresh_token"] == "rotated-rt"

    def test_refresh_request_error_raises_auth_required(self, monkeypatch):
        self._write_cache(-10)

        def _raise(url, json):
            raise httpx.RequestError("connection failed")

        monkeypatch.setattr(import_google_doc.httpx, "post", _raise)

        with pytest.raises(AuthRequiredError):
            get_credentials()

    def test_refresh_non_200_raises_auth_required(self, monkeypatch):
        self._write_cache(-10)
        monkeypatch.setattr(
            import_google_doc.httpx,
            "post",
            lambda url, json: _FakeResponse({"error": "invalid_grant"}, status_code=400),
        )

        with pytest.raises(AuthRequiredError):
            get_credentials()


class _FakeHttpResp:
    def __init__(self, status: int, reason: str):
        self.status = status
        self.reason = reason


class _FakeFilesExport:
    def __init__(self, result: bytes | None, error: HttpError | None):
        self._result = result
        self._error = error

    def execute(self) -> bytes:
        if self._error is not None:
            raise self._error
        return self._result


class _FakeFiles:
    def __init__(self, result: bytes | None, error: HttpError | None):
        self._result = result
        self._error = error

    def export(self, fileId: str, mimeType: str) -> _FakeFilesExport:
        return _FakeFilesExport(self._result, self._error)


class _FakeDriveService:
    def __init__(self, result: bytes | None = None, error: HttpError | None = None):
        self._result = result
        self._error = error

    def files(self) -> _FakeFiles:
        return _FakeFiles(self._result, self._error)


class TestExportDocHtml:
    def test_successful_export_returns_decoded_html(self, monkeypatch):
        captured = {}
        creds = object()

        def _fake_build(name, version, credentials=None):
            captured["args"] = (name, version, credentials)
            return _FakeDriveService(result=b"<html>hello</html>")

        monkeypatch.setattr(import_google_doc, "build", _fake_build)

        html = export_doc_html("doc-123", creds)

        assert html == "<html>hello</html>"
        assert captured["args"] == ("drive", "v3", creds)

    def test_403_raises_permission_denied(self, monkeypatch):
        error = HttpError(resp=_FakeHttpResp(403, "Forbidden"), content=b"{}")
        monkeypatch.setattr(
            import_google_doc, "build", lambda *a, **k: _FakeDriveService(error=error)
        )

        with pytest.raises(PermissionDeniedError):
            export_doc_html("doc-123", object())

    def test_other_http_error_raises_google_api_error_with_status_and_reason(self, monkeypatch):
        error = HttpError(resp=_FakeHttpResp(500, "Internal Server Error"), content=b"{}")
        monkeypatch.setattr(
            import_google_doc, "build", lambda *a, **k: _FakeDriveService(error=error)
        )

        with pytest.raises(GoogleApiError) as exc_info:
            export_doc_html("doc-123", object())

        assert "500" in str(exc_info.value)
        assert "Internal Server Error" in str(exc_info.value)
