import json
from pathlib import Path
from urllib.parse import quote

import httpx
import pytest
from googleapiclient.errors import HttpError

import shared.fs as fs
import tools.import_google_doc as import_google_doc
from shared.errors import (
    AuthRequiredError,
    FileAlreadyExistsError,
    GoogleApiError,
    PermissionDeniedError,
)
from tools.import_google_doc import (
    InkClerkConverter,
    convert_to_markdown,
    download_images,
    export_doc_html,
    extract_image_urls,
    get_credentials,
    get_doc_title,
    parse_doc_id,
    replace_image_references,
)

import_google_doc_tool = import_google_doc.import_google_doc


def make_project(root: Path, name: str) -> Path:
    slug = name.lower().replace(" ", "-")
    project_dir = root / slug
    inkclerk_dir = project_dir / ".inkclerk"
    inkclerk_dir.mkdir(parents=True)
    (inkclerk_dir / "project.json").write_text(
        json.dumps({"version": 1, "id": f"id-{slug}", "name": name}),
        encoding="utf-8",
    )
    return project_dir


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


class _FakeFilesGet:
    def __init__(self, title: str | None, error: HttpError | None):
        self._title = title
        self._error = error

    def execute(self) -> dict:
        if self._error is not None:
            raise self._error
        return {"name": self._title}


class _FakeFiles:
    def __init__(
        self,
        result: bytes | None = None,
        error: HttpError | None = None,
        title: str | None = None,
        title_error: HttpError | None = None,
    ):
        self._result = result
        self._error = error
        self._title = title
        self._title_error = title_error

    def export(self, fileId: str, mimeType: str) -> _FakeFilesExport:
        return _FakeFilesExport(self._result, self._error)

    def get(self, fileId: str, fields: str) -> _FakeFilesGet:
        return _FakeFilesGet(self._title, self._title_error)


class _FakeDriveService:
    def __init__(
        self,
        result: bytes | None = None,
        error: HttpError | None = None,
        title: str | None = None,
        title_error: HttpError | None = None,
    ):
        self._result = result
        self._error = error
        self._title = title
        self._title_error = title_error

    def files(self) -> _FakeFiles:
        return _FakeFiles(self._result, self._error, self._title, self._title_error)


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


class TestExtractImageUrls:
    def test_returns_urls_in_document_order(self):
        html = (
            "<p>before</p>"
            '<img src="https://example.com/a.png">'
            "<p>middle</p>"
            '<img src="https://example.com/b.png">'
        )
        assert extract_image_urls(html) == [
            "https://example.com/a.png",
            "https://example.com/b.png",
        ]

    def test_no_images_returns_empty_list(self):
        assert extract_image_urls("<p>no images here</p>") == []

    def test_does_not_strip_or_alter_span_styles(self):
        html = (
            '<span style="font-family: Arial; color: red;">styled</span>'
            '<img src="https://example.com/a.png">'
        )
        assert extract_image_urls(html) == ["https://example.com/a.png"]


class TestInkClerkConverter:
    def _convert(self, html: str) -> str:
        return InkClerkConverter(heading_style="atx", bullets="-").convert(html)

    def test_bold(self):
        assert self._convert("<b>text</b>").strip() == "**text**"
        assert self._convert("<strong>text</strong>").strip() == "**text**"

    def test_italic(self):
        assert self._convert("<i>text</i>").strip() == "*text*"
        assert self._convert("<em>text</em>").strip() == "*text*"

    def test_strikethrough(self):
        assert self._convert("<s>text</s>").strip() == "~~text~~"
        assert self._convert("<del>text</del>").strip() == "~~text~~"

    def test_headings_use_atx_not_setext(self):
        for level in range(1, 7):
            tag = f"h{level}"
            md = self._convert(f"<{tag}>Heading</{tag}>").strip()
            assert md == f"{'#' * level} Heading"
            assert "===" not in md
            assert "---" not in md

    def test_table_produces_gfm_syntax(self):
        html = (
            "<table><thead><tr><th>A</th><th>B</th></tr></thead>"
            "<tbody><tr><td>1</td><td>2</td></tr></tbody></table>"
        )
        md = self._convert(html)
        assert "| A | B |" in md
        assert "| --- | --- |" in md
        assert "| 1 | 2 |" in md

    def test_ordered_list(self):
        md = self._convert("<ol><li>first</li><li>second</li></ol>").strip()
        assert "1. first" in md
        assert "2. second" in md

    def test_unordered_list(self):
        md = self._convert("<ul><li>first</li><li>second</li></ul>").strip()
        assert "- first" in md
        assert "- second" in md

    def test_span_with_visual_style_preserved_as_inline_html(self):
        html = '<span style="font-family: Arial; color: red;">styled</span>'
        md = self._convert(html).strip()
        assert md == '<span style="font-family: Arial; color: red;">styled</span>'

    def test_span_drops_non_visual_properties(self):
        html = '<span style="margin: 0; color: red;">styled</span>'
        md = self._convert(html).strip()
        assert md == '<span style="color: red;">styled</span>'
        assert "margin" not in md

    def test_span_with_no_visual_properties_is_unwrapped(self):
        html = '<span style="margin: 0;">plain</span>'
        md = self._convert(html).strip()
        assert md == "plain"
        assert "<span" not in md

    def test_underline_element_preserved(self):
        md = self._convert("<u>text</u>").strip()
        assert md == "<u>text</u>"


class TestConvertToMarkdown:
    def test_matches_direct_converter_invocation(self):
        html = "<h1>Title</h1><p><b>bold</b> and <u>underlined</u></p>"
        expected = InkClerkConverter(heading_style="atx", bullets="-").convert(html)
        assert convert_to_markdown(html) == expected


class TestSlugifyAscii:
    def test_lowercases_and_hyphenates_spaces(self):
        assert import_google_doc._slugify_ascii("My Great Doc") == "my-great-doc"

    def test_strips_non_ascii_characters(self):
        result = import_google_doc._slugify_ascii("Café 中文 Notes")
        assert result.isascii()
        assert "notes" in result
        assert "caf" in result

    def test_all_non_ascii_falls_back_to_untitled(self):
        assert import_google_doc._slugify_ascii("中文文档") == "untitled"


class TestGetDocTitle:
    def test_returns_name_field(self, monkeypatch):
        monkeypatch.setattr(
            import_google_doc, "build", lambda *a, **k: _FakeDriveService(title="My Doc")
        )

        assert get_doc_title("doc-123", object()) == "My Doc"

    def test_403_raises_permission_denied(self, monkeypatch):
        error = HttpError(resp=_FakeHttpResp(403, "Forbidden"), content=b"{}")
        monkeypatch.setattr(
            import_google_doc, "build", lambda *a, **k: _FakeDriveService(title_error=error)
        )

        with pytest.raises(PermissionDeniedError):
            get_doc_title("doc-123", object())

    def test_other_http_error_raises_google_api_error(self, monkeypatch):
        error = HttpError(resp=_FakeHttpResp(500, "Internal Server Error"), content=b"{}")
        monkeypatch.setattr(
            import_google_doc, "build", lambda *a, **k: _FakeDriveService(title_error=error)
        )

        with pytest.raises(GoogleApiError):
            get_doc_title("doc-123", object())


class _FakeImageResponse:
    def __init__(self, content: bytes):
        self.content = content


def _make_fake_authorized_session(bytes_by_url: dict[str, bytes]):
    class _FakeAuthorizedSession:
        def __init__(self, creds):
            self.creds = creds

        def get(self, url: str) -> _FakeImageResponse:
            return _FakeImageResponse(bytes_by_url[url])

    return _FakeAuthorizedSession


class TestDownloadImages:
    def test_image_saved_to_assets_dir(self, tmp_path, monkeypatch):
        url = "https://example.com/photo.png"
        monkeypatch.setattr(
            import_google_doc, "AuthorizedSession", _make_fake_authorized_session({url: b"PNGDATA"})
        )
        assets_dir = tmp_path / "notes-assets"

        result = download_images([url], object(), assets_dir)

        assert (assets_dir / "photo.png").read_bytes() == b"PNGDATA"
        assert result[url] == "./notes-assets/photo.png"

    def test_markdown_relpath_is_dot_slash_percent_encoded(self, tmp_path, monkeypatch):
        url = "https://example.com/my%20photo.png"
        monkeypatch.setattr(
            import_google_doc, "AuthorizedSession", _make_fake_authorized_session({url: b"data"})
        )
        assets_dir = tmp_path / "doc-assets"

        result = download_images([url], object(), assets_dir)

        assert (assets_dir / "my photo.png").exists()
        assert result[url] == "./doc-assets/my%20photo.png"

    def test_over_255_byte_filename_truncated_on_disk_and_in_relpath(self, tmp_path, monkeypatch):
        long_name = ("a" * 300) + ".png"
        url = f"https://example.com/{long_name}"
        monkeypatch.setattr(
            import_google_doc, "AuthorizedSession", _make_fake_authorized_session({url: b"data"})
        )
        assets_dir = tmp_path / "doc-assets"

        result = download_images([url], object(), assets_dir)

        saved = list(assets_dir.iterdir())
        assert len(saved) == 1
        saved_name = saved[0].name
        assert len(saved_name.encode("utf-8")) <= 255
        assert saved_name.endswith(".png")
        assert result[url] == f"./doc-assets/{quote(saved_name, safe='')}"

    def test_cjk_filename_raw_unicode_on_disk_percent_encoded_in_relpath(self, tmp_path, monkeypatch):
        url = "https://example.com/%E6%9C%83%E8%AD%B0.png"
        monkeypatch.setattr(
            import_google_doc, "AuthorizedSession", _make_fake_authorized_session({url: b"data"})
        )
        assets_dir = tmp_path / "doc-assets"

        result = download_images([url], object(), assets_dir)

        assert (assets_dir / "會議.png").exists()
        assert result[url] == "./doc-assets/%E6%9C%83%E8%AD%B0.png"

    def test_multiple_images_all_downloaded(self, tmp_path, monkeypatch):
        url_a = "https://example.com/a.png"
        url_b = "https://example.com/b.png"
        monkeypatch.setattr(
            import_google_doc,
            "AuthorizedSession",
            _make_fake_authorized_session({url_a: b"A", url_b: b"B"}),
        )
        assets_dir = tmp_path / "doc-assets"

        result = download_images([url_a, url_b], object(), assets_dir)

        assert (assets_dir / "a.png").read_bytes() == b"A"
        assert (assets_dir / "b.png").read_bytes() == b"B"
        assert set(result.keys()) == {url_a, url_b}

    def test_assets_dir_created_by_call(self, tmp_path, monkeypatch):
        url = "https://example.com/a.png"
        monkeypatch.setattr(
            import_google_doc, "AuthorizedSession", _make_fake_authorized_session({url: b"data"})
        )
        assets_dir = tmp_path / "not-yet-created-assets"
        assert not assets_dir.exists()

        download_images([url], object(), assets_dir)

        assert assets_dir.is_dir()


class TestReplaceImageReferences:
    def test_replaces_single_url(self):
        markdown = "![alt](https://example.com/a.png)"

        result = replace_image_references(
            markdown, {"https://example.com/a.png": "./doc-assets/a.png"}
        )

        assert result == "![alt](./doc-assets/a.png)"

    def test_replaces_multiple_urls(self):
        markdown = "![a](https://example.com/a.png) and ![b](https://example.com/b.png)"

        result = replace_image_references(
            markdown,
            {
                "https://example.com/a.png": "./doc-assets/a.png",
                "https://example.com/b.png": "./doc-assets/b.png",
            },
        )

        assert result == "![a](./doc-assets/a.png) and ![b](./doc-assets/b.png)"


class TestImportGoogleDoc:
    def _setup(self, tmp_path, monkeypatch, html, title=None):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        monkeypatch.setattr(import_google_doc, "get_credentials", lambda: object())
        monkeypatch.setattr(
            import_google_doc,
            "build",
            lambda *a, **k: _FakeDriveService(result=html.encode("utf-8"), title=title),
        )
        return make_project(tmp_path, "Alpha")

    def test_default_filename_is_slugified_doc_title(self, tmp_path, monkeypatch):
        self._setup(tmp_path, monkeypatch, "<h1>Hello</h1>", title="My Great Doc")

        result = import_google_doc_tool(google_doc_url_or_id="doc-123", project_name="Alpha")

        expected_path = tmp_path / "alpha" / "my-great-doc.md"
        assert result["doc_path"] == str(expected_path)
        assert expected_path.exists()

    def test_explicit_filename_overrides_title_fetch(self, tmp_path, monkeypatch):
        # title is left as None; if get_doc_title were called anyway, slugifying
        # None would raise AttributeError and fail this test.
        self._setup(tmp_path, monkeypatch, "<h1>Hi</h1>")

        result = import_google_doc_tool(
            google_doc_url_or_id="doc-123", project_name="Alpha", filename="custom-name"
        )

        assert result["doc_path"] == str(tmp_path / "alpha" / "custom-name.md")

    def test_frontmatter_prepended_with_id_created_last_modified(self, tmp_path, monkeypatch):
        self._setup(tmp_path, monkeypatch, "<h1>Hello</h1><p>World</p>", title="Doc")

        result = import_google_doc_tool(google_doc_url_or_id="doc-123", project_name="Alpha")

        text = Path(result["doc_path"]).read_text(encoding="utf-8")
        assert text.startswith("---\n")
        assert f"id: {result['doc_id']}" in text
        assert "created:" in text
        assert "lastModified:" in text
        assert "# Hello" in text
        assert "World" in text

    def test_raises_file_already_exists_and_skips_export(self, tmp_path, monkeypatch):
        project_path = self._setup(tmp_path, monkeypatch, "<h1>Hi</h1>")
        (project_path / "existing.md").write_text("already here", encoding="utf-8")

        def _fail_export(*a, **k):
            raise AssertionError("should not export HTML when target already exists")

        monkeypatch.setattr(import_google_doc, "export_doc_html", _fail_export)

        with pytest.raises(FileAlreadyExistsError):
            import_google_doc_tool(
                google_doc_url_or_id="doc-123", project_name="Alpha", filename="existing"
            )

    def test_returns_doc_path_doc_id_and_empty_dropped_styles(self, tmp_path, monkeypatch):
        self._setup(tmp_path, monkeypatch, "<h1>Hi</h1>", title="Doc")

        result = import_google_doc_tool(google_doc_url_or_id="doc-123", project_name="Alpha")

        assert set(result.keys()) == {"doc_path", "doc_id", "dropped_styles"}
        assert result["dropped_styles"] == []
        assert result["doc_id"]

    def test_no_images_skips_assets_dir_creation(self, tmp_path, monkeypatch):
        self._setup(tmp_path, monkeypatch, "<h1>No images</h1>", title="Doc")

        result = import_google_doc_tool(google_doc_url_or_id="doc-123", project_name="Alpha")

        assets_dir = Path(result["doc_path"]).with_name("doc-assets")
        assert not assets_dir.exists()

    def test_images_present_creates_assets_dir_and_rewrites_references(self, tmp_path, monkeypatch):
        image_url = "https://example.com/photo.png"
        html = f'<h1>Title</h1><img src="{image_url}">'
        self._setup(tmp_path, monkeypatch, html, title="Doc")
        monkeypatch.setattr(
            import_google_doc,
            "AuthorizedSession",
            _make_fake_authorized_session({image_url: b"PNGDATA"}),
        )

        result = import_google_doc_tool(google_doc_url_or_id="doc-123", project_name="Alpha")

        assets_dir = Path(result["doc_path"]).with_name("doc-assets")
        assert (assets_dir / "photo.png").read_bytes() == b"PNGDATA"
        text = Path(result["doc_path"]).read_text(encoding="utf-8")
        assert "./doc-assets/photo.png" in text
        assert image_url not in text

    def test_subdirectory_argument_places_file_correctly(self, tmp_path, monkeypatch):
        self._setup(tmp_path, monkeypatch, "<h1>Hi</h1>", title="Doc")

        result = import_google_doc_tool(
            google_doc_url_or_id="doc-123", project_name="Alpha", subdirectory="imports"
        )

        assert result["doc_path"] == str(tmp_path / "alpha" / "imports" / "doc.md")
