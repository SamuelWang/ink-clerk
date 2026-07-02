from pathlib import Path

import pytest

import shared.fs as fs
from shared.errors import DocumentNotFoundError, NoDraftError
from shared.frontmatter import parse, write
from tools.drafts import accept_draft, get_diff, get_draft, propose_edit, reject_draft


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def make_project(root: Path, name: str) -> Path:
    import json

    slug = name.lower().replace(" ", "-")
    project_dir = root / slug
    inkclerk_dir = project_dir / ".inkclerk"
    inkclerk_dir.mkdir(parents=True)
    (inkclerk_dir / "project.json").write_text(
        json.dumps(
            {
                "version": 1,
                "id": f"id-{slug}",
                "name": name,
                "description": "",
                "created": "2026-01-01T00:00:00+00:00",
                "lastModified": "2026-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    return project_dir


def make_draft(project_path: Path, rel_path: str, content: str = "Draft body.\n") -> Path:
    draft_path = project_path / ".inkclerk" / "drafts" / rel_path
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text(content, encoding="utf-8")
    return draft_path


# ---------------------------------------------------------------------------
# TestProposeEdit
# ---------------------------------------------------------------------------


class TestProposeEdit:
    def test_creates_draft_file_verbatim_no_frontmatter(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md")

        result = propose_edit(project_name="Alpha", doc_path="notes.md", content="New body.\n")

        draft_path = project_dir / ".inkclerk" / "drafts" / "notes.md"
        assert draft_path.exists()
        text = draft_path.read_text(encoding="utf-8")
        assert text == "New body.\n"
        assert not text.startswith("---\n")
        assert result["draft_path"] == str(draft_path)

    def test_creates_intermediate_directories(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "q3/notes.md")

        propose_edit(project_name="Alpha", doc_path="q3/notes.md", content="Body.\n")

        assert (project_dir / ".inkclerk" / "drafts" / "q3" / "notes.md").exists()

    def test_overwritten_false_on_first_write(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md")

        result = propose_edit(project_name="Alpha", doc_path="notes.md", content="Body.\n")
        assert result["overwritten"] is False

    def test_overwritten_true_and_content_replaced(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md")
        draft_path = make_draft(project_dir, "notes.md", content="Old draft.\n")

        result = propose_edit(project_name="Alpha", doc_path="notes.md", content="New draft.\n")

        assert result["overwritten"] is True
        assert draft_path.read_text(encoding="utf-8") == "New draft.\n"

    def test_raises_document_not_found_when_formal_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        make_project(tmp_path, "Alpha")

        with pytest.raises(DocumentNotFoundError):
            propose_edit(project_name="Alpha", doc_path="notes.md", content="x")


# ---------------------------------------------------------------------------
# TestGetDraft
# ---------------------------------------------------------------------------


class TestGetDraft:
    def test_returns_content_and_draft_path(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md")
        draft_path = make_draft(project_dir, "notes.md", content="Draft body.\n")

        result = get_draft(project_name="Alpha", doc_path="notes.md")

        assert result["content"] == "Draft body.\n"
        assert result["draft_path"] == str(draft_path)

    def test_raises_no_draft_when_none_exists(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md")

        with pytest.raises(NoDraftError):
            get_draft(project_name="Alpha", doc_path="notes.md")

    def test_raises_document_not_found_when_formal_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        make_project(tmp_path, "Alpha")

        with pytest.raises(DocumentNotFoundError):
            get_draft(project_name="Alpha", doc_path="notes.md")


# ---------------------------------------------------------------------------
# TestGetDiff
# ---------------------------------------------------------------------------


class TestGetDiff:
    def test_returns_unified_diff_with_correct_counts(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md", content="line1\nline2\n")
        make_draft(project_dir, "notes.md", content="line1\nline2 changed\nline3\n")

        result = get_diff(project_name="Alpha", doc_path="notes.md")

        assert result["diff"].startswith("--- formal\n")
        assert "+++ draft\n" in result["diff"]
        assert "@@" in result["diff"]
        assert result["additions"] == 2
        assert result["deletions"] == 1

    def test_empty_diff_when_content_identical(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md", content="Same content.\n")
        make_draft(project_dir, "notes.md", content="Same content.\n")

        result = get_diff(project_name="Alpha", doc_path="notes.md")

        assert result["diff"] == ""
        assert result["additions"] == 0
        assert result["deletions"] == 0

    def test_diffs_against_body_not_raw_frontmatter_text(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        # make_document wraps content in real YAML frontmatter via shared.frontmatter.write
        make_document(project_dir, "notes.md", content="Same content.\n")
        make_draft(project_dir, "notes.md", content="Same content.\n")

        result = get_diff(project_name="Alpha", doc_path="notes.md")

        assert result["diff"] == ""

    def test_raises_no_draft_when_none_exists(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md")

        with pytest.raises(NoDraftError):
            get_diff(project_name="Alpha", doc_path="notes.md")

    def test_raises_document_not_found_when_formal_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        make_project(tmp_path, "Alpha")

        with pytest.raises(DocumentNotFoundError):
            get_diff(project_name="Alpha", doc_path="notes.md")


# ---------------------------------------------------------------------------
# TestAcceptDraft
# ---------------------------------------------------------------------------


class TestAcceptDraft:
    def test_writes_draft_body_to_formal_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        doc_path = make_document(project_dir, "notes.md", content="Old body.\n")
        make_draft(project_dir, "notes.md", content="New body.\n")

        accept_draft(project_name="Alpha", doc_path="notes.md")

        _, body = parse(doc_path.read_text(encoding="utf-8"))
        assert body == "New body.\n"

    def test_preserves_id_and_created_updates_last_modified(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        doc_path = make_document(
            project_dir,
            "notes.md",
            doc_id="d1",
            created="2026-01-01T00:00:00+00:00",
            last_modified="2026-01-01T00:00:00+00:00",
        )
        make_draft(project_dir, "notes.md", content="New body.\n")

        accept_draft(project_name="Alpha", doc_path="notes.md")

        meta, _ = parse(doc_path.read_text(encoding="utf-8"))
        assert meta["id"] == "d1"
        assert meta["created"] == "2026-01-01T00:00:00+00:00"
        assert meta["lastModified"] != "2026-01-01T00:00:00+00:00"

    def test_deletes_draft_after_accept(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md")
        draft_path = make_draft(project_dir, "notes.md")

        accept_draft(project_name="Alpha", doc_path="notes.md")

        assert not draft_path.exists()

    def test_returns_doc_path(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        doc_path = make_document(project_dir, "notes.md")
        make_draft(project_dir, "notes.md")

        result = accept_draft(project_name="Alpha", doc_path="notes.md")

        assert result["doc_path"] == str(doc_path)

    def test_raises_no_draft_when_none_exists(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md")

        with pytest.raises(NoDraftError):
            accept_draft(project_name="Alpha", doc_path="notes.md")

    def test_raises_document_not_found_when_formal_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        make_project(tmp_path, "Alpha")

        with pytest.raises(DocumentNotFoundError):
            accept_draft(project_name="Alpha", doc_path="notes.md")


# ---------------------------------------------------------------------------
# TestRejectDraft
# ---------------------------------------------------------------------------


class TestRejectDraft:
    def test_deletes_draft_without_modifying_formal(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        doc_path = make_document(project_dir, "notes.md", content="Formal body.\n")
        draft_path = make_draft(project_dir, "notes.md")
        before = doc_path.read_text(encoding="utf-8")

        reject_draft(project_name="Alpha", doc_path="notes.md")

        assert not draft_path.exists()
        assert doc_path.read_text(encoding="utf-8") == before

    def test_returns_draft_path(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md")
        draft_path = make_draft(project_dir, "notes.md")

        result = reject_draft(project_name="Alpha", doc_path="notes.md")

        assert result["draft_path"] == str(draft_path)

    def test_raises_no_draft_when_none_exists(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md")

        with pytest.raises(NoDraftError):
            reject_draft(project_name="Alpha", doc_path="notes.md")

    def test_raises_document_not_found_when_formal_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        make_project(tmp_path, "Alpha")

        with pytest.raises(DocumentNotFoundError):
            reject_draft(project_name="Alpha", doc_path="notes.md")
