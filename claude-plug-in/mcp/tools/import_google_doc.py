import json
import os
import re
import time
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import httpx
import markdownify
from bs4 import BeautifulSoup
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from shared.errors import AuthRequiredError, GoogleApiError, PermissionDeniedError
from shared.fs import ensure_dir

_DOC_ID_URL_RE = re.compile(r"/document/d/([a-zA-Z0-9_-]+)")


def parse_doc_id(google_doc_url_or_id: str) -> str:
    match = _DOC_ID_URL_RE.search(google_doc_url_or_id)
    if match:
        return match.group(1)
    if "docs.google.com" in google_doc_url_or_id:
        raise GoogleApiError("Cannot parse Google Doc URL")
    return google_doc_url_or_id


TOKEN_CACHE_PATH = Path.home() / ".config" / "inkclerk" / "google-token.json"
POLL_INTERVAL_SECONDS = 2
POLL_TIMEOUT_SECONDS = 120


def _auth_service_url() -> str:
    url = os.environ.get("INKCLERK_AUTH_SERVICE_URL")
    if not url:
        raise AuthRequiredError(
            "INKCLERK_AUTH_SERVICE_URL is not set; cannot reach the hosted "
            "Google OAuth broker"
        )
    return url


def _load_cached_token() -> dict | None:
    if not TOKEN_CACHE_PATH.exists():
        return None
    return json.loads(TOKEN_CACHE_PATH.read_text(encoding="utf-8"))


def _write_cached_token(token_data: dict) -> None:
    ensure_dir(TOKEN_CACHE_PATH.parent)
    TOKEN_CACHE_PATH.write_text(json.dumps(token_data), encoding="utf-8")


def _compute_expiry(expires_in: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()


def _poll_for_token(auth_service_url: str, session_id: str) -> dict:
    webbrowser.open(f"{auth_service_url}/auth/google/start?session_id={session_id}")

    max_attempts = POLL_TIMEOUT_SECONDS // POLL_INTERVAL_SECONDS
    for _ in range(max_attempts):
        try:
            response = httpx.get(f"{auth_service_url}/auth/google/session/{session_id}")
        except httpx.RequestError as e:
            raise AuthRequiredError(
                "Could not reach the hosted Google OAuth broker while polling "
                "for the login result"
            ) from e

        payload = response.json()
        status = payload.get("status")
        if status == "ready":
            return {
                "access_token": payload["access_token"],
                "refresh_token": payload["refresh_token"],
                "expiry": _compute_expiry(payload["expires_in"]),
            }
        if status == "expired":
            raise AuthRequiredError(
                "The Google login session expired before it was completed; "
                "please try again"
            )
        time.sleep(POLL_INTERVAL_SECONDS)

    raise AuthRequiredError(
        "Timed out waiting for the Google login to complete in the browser"
    )


def _refresh_token(auth_service_url: str, cached: dict) -> dict:
    try:
        response = httpx.post(
            f"{auth_service_url}/auth/refresh",
            json={"refresh_token": cached["refresh_token"]},
        )
    except httpx.RequestError as e:
        raise AuthRequiredError(
            "Could not reach the hosted Google OAuth broker to refresh the "
            "access token"
        ) from e

    if response.status_code != 200:
        raise AuthRequiredError(
            "The hosted Google OAuth broker rejected the refresh token; "
            "please sign in again"
        )

    payload = response.json()
    return {
        "access_token": payload["access_token"],
        "refresh_token": payload.get("refresh_token", cached["refresh_token"]),
        "expiry": _compute_expiry(payload["expires_in"]),
    }


def get_credentials() -> Credentials:
    auth_service_url = _auth_service_url()
    cached = _load_cached_token()

    if cached is None:
        token_data = _poll_for_token(auth_service_url, session_id=str(uuid4()))
        _write_cached_token(token_data)
    elif datetime.now(timezone.utc) < datetime.fromisoformat(cached["expiry"]):
        token_data = cached
    else:
        token_data = _refresh_token(auth_service_url, cached)
        _write_cached_token(token_data)

    return Credentials(token=token_data["access_token"])


def export_doc_html(doc_id: str, creds: Credentials) -> str:
    service = build("drive", "v3", credentials=creds)
    try:
        html_bytes = service.files().export(fileId=doc_id, mimeType="text/html").execute()
    except HttpError as e:
        if e.resp.status == 403:
            raise PermissionDeniedError(f"No permission to access Google Doc {doc_id}") from e
        raise GoogleApiError(f"Drive API error {e.resp.status}: {e.reason}") from e
    return html_bytes.decode("utf-8")


def extract_image_urls(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    return [img["src"] for img in soup.find_all("img") if img.get("src")]


class InkClerkConverter(markdownify.MarkdownConverter):
    VISUAL_PROPS = {"color", "background-color", "font-family", "font-size", "text-decoration"}

    def convert_span(self, el, text, parent_tags):
        style = el.get("style", "")
        kept = [
            p.strip() for p in style.split(";")
            if p.strip() and p.strip().split(":")[0].strip() in self.VISUAL_PROPS
        ]
        if kept:
            return f'<span style="{"; ".join(kept)};">{text}</span>'
        return text

    def convert_u(self, el, text, parent_tags):
        return f"<u>{text}</u>"


def convert_to_markdown(html: str) -> str:
    return InkClerkConverter(heading_style="atx", bullets="-").convert(html)
