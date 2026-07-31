import os
import re
import time
import webbrowser
from datetime import datetime, timezone
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

from shared.mcp_instance import mcp
from shared.errors import (
    AuthRequiredError,
    FileAlreadyExistsError,
    GoogleApiError,
    PermissionDeniedError,
)
from shared.fs import ensure_dir, resolve_project, truncate_basename
from shared.frontmatter import write

CHECK_INTERVAL_SECONDS = 2
CHECK_ATTEMPTS = 5  # ~10s total — smooths a race between "user says done" and the
                    # relay recording it; not a substitute for waiting on the user


def _web_app_url() -> str:
    url = os.environ.get("INKCLERK_WEB_APP_URL")
    if not url:
        raise AuthRequiredError(
            "INKCLERK_WEB_APP_URL is not set; cannot open the InkClerk web app "
            "to sign in with Google"
        )
    return url


def _web_api_url() -> str:
    url = os.environ.get("INKCLERK_WEB_API_URL")
    if not url:
        raise AuthRequiredError(
            "INKCLERK_WEB_API_URL is not set; cannot poll for the Google sign-in result"
        )
    return url


def _start_import_session() -> dict:
    web_app_url = _web_app_url()
    _web_api_url()  # validate both env vars up front, before opening a browser
    session_id = str(uuid4())
    sign_in_url = f"{web_app_url}/import/google-doc?session_id={session_id}"
    webbrowser.open(sign_in_url)  # best-effort convenience; never relied upon
    return {"status": "pending", "session_id": session_id, "sign_in_url": sign_in_url}


def _check_session_ready(web_api_url: str, session_id: str, sign_in_url: str) -> dict:
    for _ in range(CHECK_ATTEMPTS):
        try:
            response = httpx.get(f"{web_api_url}/import/google-doc/session/{session_id}")
        except httpx.RequestError:
            time.sleep(CHECK_INTERVAL_SECONDS)
            continue

        payload = response.json()
        status = payload.get("status")
        if status == "ready":
            return {
                "access_token": payload["access_token"],
                "file_id": payload["file_id"],
                "file_name": payload["file_name"],
                "resource_key": payload.get("resource_key", ""),
            }
        if status == "expired":
            raise AuthRequiredError(
                "The Google sign-in session expired. Start a new import "
                "(call without session_id) to get a fresh link."
            )
        time.sleep(CHECK_INTERVAL_SECONDS)

    raise AuthRequiredError(
        "Sign-in doesn't look complete yet. Make sure you opened "
        f"{sign_in_url}, finished signing in with Google, and picked the "
        "document — then ask to check again."
    )


def _await_credentials(session_id: str) -> tuple[Credentials, dict]:
    web_app_url = _web_app_url()
    sign_in_url = f"{web_app_url}/import/google-doc?session_id={session_id}"
    token_data = _check_session_ready(_web_api_url(), session_id, sign_in_url)
    picked = {
        "file_id": token_data["file_id"],
        "file_name": token_data["file_name"],
        "resource_key": token_data["resource_key"],
    }
    return Credentials(token=token_data["access_token"]), picked


def _add_resource_key_header(request, doc_id: str, resource_key: str) -> None:
    if resource_key:
        request.headers["X-Goog-Drive-Resource-Keys"] = f"{doc_id}/{resource_key}"


def export_doc_html(doc_id: str, creds: Credentials, resource_key: str = "") -> str:
    service = build("drive", "v3", credentials=creds)
    request = service.files().export(fileId=doc_id, mimeType="text/html")
    _add_resource_key_header(request, doc_id, resource_key)
    try:
        html_bytes = request.execute()
    except HttpError as e:
        if e.resp.status == 403:
            raise PermissionDeniedError(
                f"No permission to access Google Doc {doc_id}: {e.reason}"
            ) from e
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


def get_doc_title(doc_id: str, creds: Credentials, resource_key: str = "") -> str:
    service = build("drive", "v3", credentials=creds)
    request = service.files().get(fileId=doc_id, fields="name")
    _add_resource_key_header(request, doc_id, resource_key)
    try:
        meta = request.execute()
    except HttpError as e:
        if e.resp.status == 403:
            raise PermissionDeniedError(
                f"No permission to access Google Doc {doc_id}: {e.reason}"
            ) from e
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
    project_name: str,
    filename: str = "",
    subdirectory: str = "",
    session_id: str = "",
) -> dict:
    """Import a Google Doc into an InkClerk project as Markdown.

    Call this twice. First, call it with session_id omitted — it opens a
    browser for Google sign-in + Picker (best-effort) and returns
    immediately with {"status": "pending", "session_id", "sign_in_url"}.
    Relay sign_in_url to the user and wait for them to confirm they're
    done. Then call this again with that same session_id to complete the
    import — this does one quick check, not a long wait, so only call it
    after the user has actually confirmed.
    """
    if not session_id:
        return _start_import_session()

    creds, picked = _await_credentials(session_id)
    doc_id = picked["file_id"]
    resource_key = picked["resource_key"]
    project_path, _ = resolve_project(project_name)

    if filename:
        output_filename = filename
    else:
        output_filename = _slugify_ascii(get_doc_title(doc_id, creds, resource_key))

    doc_path = project_path / subdirectory / f"{output_filename}.md"
    if doc_path.exists():
        raise FileAlreadyExistsError(f"Document '{output_filename}.md' already exists")

    html = export_doc_html(doc_id, creds, resource_key)

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
