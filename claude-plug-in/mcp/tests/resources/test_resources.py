import json
from pathlib import Path
from urllib.parse import quote

import shared.fs as fs
from resources.resources import dispatch
from shared.frontmatter import write

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_project(root: Path, name: str, project_id: str = "test-id") -> Path:
    slug = name.lower().replace(" ", "-")
    project_dir = root / slug
    inkclerk_dir = project_dir / ".inkclerk"
    inkclerk_dir.mkdir(parents=True)
    (inkclerk_dir / "project.json").write_text(
        json.dumps(
            {
                "version": 1,
                "id": project_id,
                "name": name,
                "description": "A test project",
                "created": "2026-01-01T00:00:00+00:00",
                "lastModified": "2026-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    return project_dir


def make_document(
    project_path: Path,
    rel_path: str,
    doc_id: str = "doc-id",
    created: str = "2026-01-01T00:00:00+00:00",
    last_modified: str = "2026-01-01T00:00:00+00:00",
    content: str = "# Hello\n\nBody text.\n",
) -> Path:
    doc_path = project_path / rel_path
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    meta = {"id": doc_id, "created": created, "lastModified": last_modified}
    doc_path.write_text(write(meta, content), encoding="utf-8")
    return doc_path


def make_draft(project_path: Path, rel_path: str, content: str = "Draft body.\n") -> Path:
    draft_path = project_path / ".inkclerk" / "drafts" / rel_path
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text(content, encoding="utf-8")
    return draft_path


# ---------------------------------------------------------------------------
# TestListProjectsResource
# ---------------------------------------------------------------------------


class TestListProjectsResource:
    def test_empty_root_returns_empty_array(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)

        result = json.loads(dispatch("projects"))

        assert result == []

    def test_matches_list_projects_schema(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Meeting Notes", project_id="uuid-123")

        result = json.loads(dispatch("projects"))

        assert len(result) == 1
        entry = result[0]
        assert entry["path"] == str(project_dir)
        assert entry["id"] == "uuid-123"
        assert entry["name"] == "Meeting Notes"
        assert entry["description"] == "A test project"
        assert entry["last_modified"] == "2026-01-01T00:00:00+00:00"


# ---------------------------------------------------------------------------
# TestProjectResource
# ---------------------------------------------------------------------------


class TestProjectResource:
    def test_returns_project_metadata_and_documents(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Meeting Notes", project_id="uuid-123")
        make_document(project_dir, "notes.md", doc_id="doc-1")

        result = json.loads(dispatch(f"project?name={quote('Meeting Notes')}"))

        assert result["id"] == "uuid-123"
        assert result["name"] == "Meeting Notes"
        assert result["description"] == "A test project"
        assert result["created"] == "2026-01-01T00:00:00+00:00"
        assert result["last_modified"] == "2026-01-01T00:00:00+00:00"
        assert len(result["documents"]) == 1
        assert result["documents"][0]["doc_id"] == "doc-1"

    def test_has_draft_reflects_actual_draft_existence(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md")
        make_draft(project_dir, "notes.md")

        result = json.loads(dispatch(f"project?name={quote('Alpha')}"))

        assert result["documents"][0]["has_draft"] is True

    def test_no_draft_present(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md")

        result = json.loads(dispatch(f"project?name={quote('Alpha')}"))

        assert result["documents"][0]["has_draft"] is False

    def test_unknown_project_returns_error_payload(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)

        result = json.loads(dispatch(f"project?name={quote('Nonexistent')}"))

        assert result["error"] == "PROJECT_NOT_FOUND"
        assert "message" in result


# ---------------------------------------------------------------------------
# TestDocumentResource
# ---------------------------------------------------------------------------


class TestDocumentResource:
    def test_returns_document_content_and_metadata(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md", doc_id="doc-1", content="# Title\n\nBody.\n")

        uri = f"document?project={quote('Alpha')}&path={quote('notes.md')}"
        result = json.loads(dispatch(uri))

        assert result["doc_id"] == "doc-1"
        assert result["content"] == "# Title\n\nBody.\n"
        assert result["last_modified"] == "2026-01-01T00:00:00+00:00"
        assert result["has_draft"] is False

    def test_subdirectory_path_round_trips_when_called_directly(self, tmp_path, monkeypatch):
        # A '/' in the path query value cannot be matched by the live MCP
        # protocol's template regex ([^/]+), but calling dispatch() directly
        # (as tests do) bypasses that regex entirely, so this must still work.
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes/meeting.md", doc_id="doc-2")

        uri = f"document?project={quote('Alpha')}&path={quote('notes/meeting.md')}"
        result = json.loads(dispatch(uri))

        assert result["doc_id"] == "doc-2"

    def test_unknown_document_returns_error_payload(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        make_project(tmp_path, "Alpha")

        uri = f"document?project={quote('Alpha')}&path={quote('missing.md')}"
        result = json.loads(dispatch(uri))

        assert result["error"] == "FILE_NOT_FOUND"
        assert "message" in result


# ---------------------------------------------------------------------------
# TestDraftResource
# ---------------------------------------------------------------------------


class TestDraftResource:
    def test_returns_draft_content_and_path(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md")
        draft_path = make_draft(project_dir, "notes.md", content="Revised body.\n")

        uri = f"draft?project={quote('Alpha')}&path={quote('notes.md')}"
        result = json.loads(dispatch(uri))

        assert result["content"] == "Revised body.\n"
        assert result["draft_path"] == str(draft_path)

    def test_no_draft_returns_error_payload(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md")

        uri = f"draft?project={quote('Alpha')}&path={quote('notes.md')}"
        result = json.loads(dispatch(uri))

        assert result["error"] == "NO_DRAFT"
        assert "message" in result
