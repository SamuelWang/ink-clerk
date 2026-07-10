import json
import os
import re
import time
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urlsplit
from uuid import uuid4

import httpx
import markdownify
from bs4 import BeautifulSoup
from google.auth.transport.requests import AuthorizedSession
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from uuid_extensions import uuid7

from main import mcp
from shared.errors import (
    AuthRequiredError,
    FileAlreadyExistsError,
    GoogleApiError,
    PermissionDeniedError,
)
from shared.fs import ensure_dir, resolve_project, truncate_basename
from shared.frontmatter import write

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


def _slugify_ascii(name: str) -> str:
    s = name.lower().encode("ascii", errors="ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "untitled"


def get_doc_title(doc_id: str, creds: Credentials) -> str:
    service = build("drive", "v3", credentials=creds)
    try:
        meta = service.files().get(fileId=doc_id, fields="name").execute()
    except HttpError as e:
        if e.resp.status == 403:
            raise PermissionDeniedError(f"No permission to access Google Doc {doc_id}") from e
        raise GoogleApiError(f"Drive API error {e.resp.status}: {e.reason}") from e
    return meta["name"]


def _image_filename_from_url(url: str) -> str:
    raw = unquote(PurePosixPath(urlsplit(url).path).name) or "image"
    return truncate_basename(raw)


def download_images(
    image_urls: list[str], creds: Credentials, assets_dir: Path
) -> dict[str, str]:
    ensure_dir(assets_dir)
    session = AuthorizedSession(creds)
    url_to_relpath: dict[str, str] = {}
    for url in image_urls:
        filename = _image_filename_from_url(url)
        response = session.get(url)
        (assets_dir / filename).write_bytes(response.content)
        url_to_relpath[url] = f"./{assets_dir.name}/{quote(filename, safe='')}"
    return url_to_relpath


def replace_image_references(markdown: str, url_to_relpath: dict[str, str]) -> str:
    for url, relpath in url_to_relpath.items():
        markdown = markdown.replace(url, relpath)
    return markdown


@mcp.tool()
def import_google_doc(
    google_doc_url_or_id: str,
    project_name: str,
    filename: str = "",
    subdirectory: str = "",
) -> dict:
    doc_id = parse_doc_id(google_doc_url_or_id)
    creds = get_credentials()
    project_path, _ = resolve_project(project_name)

    output_filename = filename or _slugify_ascii(get_doc_title(doc_id, creds))
    doc_path = project_path / subdirectory / f"{output_filename}.md"
    if doc_path.exists():
        raise FileAlreadyExistsError(f"Document '{output_filename}.md' already exists")

    html = export_doc_html(doc_id, creds)
    image_urls = extract_image_urls(html)
    markdown = convert_to_markdown(html)

    if image_urls:
        assets_dir = doc_path.with_name(f"{doc_path.stem}-assets")
        url_to_relpath = download_images(image_urls, creds, assets_dir)
        markdown = replace_image_references(markdown, url_to_relpath)

    ensure_dir(doc_path.parent)
    new_doc_id = uuid7(as_type="str")
    now = datetime.now(timezone.utc).isoformat()
    meta = {"id": new_doc_id, "created": now, "lastModified": now}
    doc_path.write_text(write(meta, markdown), encoding="utf-8")

    return {"doc_path": str(doc_path), "doc_id": new_doc_id, "dropped_styles": []}
