import os
import time
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from oauthlib.oauth2.rfc6749.errors import OAuth2Error
from pydantic import BaseModel

router = APIRouter(prefix="/auth")

SCOPES = [
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

SESSION_TTL_SECONDS = 5 * 60

_session_store: dict[str, dict] = {}


def _build_flow() -> Flow:
    client_config = {
        "web": {
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = Flow.from_client_config(client_config, scopes=SCOPES)
    flow.redirect_uri = f"{os.environ['PUBLIC_BASE_URL']}/auth/google/callback"
    return flow


@router.get("/google/start")
def google_start(session_id: str) -> RedirectResponse:
    flow = _build_flow()
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        state=session_id,
    )
    return RedirectResponse(authorization_url, status_code=302)


def _error_page(message: str) -> HTMLResponse:
    return HTMLResponse(
        f"<html><body><h1>Authentication failed</h1><p>{message}</p></body></html>",
        status_code=400,
    )


@router.get("/google/callback")
def google_callback(code: str | None = None, state: str | None = None) -> HTMLResponse:
    if not code or not state:
        return _error_page("Missing 'code' or 'state' parameter.")

    flow = _build_flow()
    try:
        flow.fetch_token(code=code)
    except OAuth2Error:
        return _error_page("Google rejected the authorization code.")

    creds = flow.credentials
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    expires_in = int((creds.expiry - now).total_seconds())
    _session_store[state] = {
        "status": "ready",
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "expires_in": expires_in,
        "created_at": time.time(),
    }
    return HTMLResponse(
        "<html><body><h1>Authentication complete</h1>"
        "<p>You can return to your terminal.</p></body></html>"
    )


@router.get("/google/session/{session_id}")
def google_session(session_id: str) -> dict:
    entry = _session_store.get(session_id)
    if entry is None:
        return {"status": "pending"}
    if entry["status"] == "expired":
        return {"status": "expired"}

    age = time.time() - entry["created_at"]
    if age > SESSION_TTL_SECONDS:
        _session_store[session_id] = {"status": "expired"}
        return {"status": "expired"}

    # Single-claim: tombstone now so any future poll for this session_id (a
    # duplicate retry, or a poll long after this one) sees "expired" instead
    # of re-issuing these tokens or reverting to "pending".
    _session_store[session_id] = {"status": "expired"}
    return {
        "status": "ready",
        "access_token": entry["access_token"],
        "refresh_token": entry["refresh_token"],
        "expires_in": entry["expires_in"],
    }


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh")
def refresh(body: RefreshRequest) -> JSONResponse:
    creds = Credentials(
        token=None,
        refresh_token=body.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
    )
    try:
        creds.refresh(GoogleAuthRequest())
    except RefreshError:
        return JSONResponse(
            status_code=400,
            content={"error": "Google rejected the refresh token."},
        )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    expires_in = int((creds.expiry - now).total_seconds())
    payload = {"access_token": creds.token, "expires_in": expires_in}
    if creds.refresh_token != body.refresh_token:
        payload["refresh_token"] = creds.refresh_token
    return JSONResponse(content=payload)
