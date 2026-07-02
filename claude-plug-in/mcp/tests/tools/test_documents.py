from pathlib import Path

import pytest

import shared.fs as fs
from shared.errors import DocumentNotFoundError, FileAlreadyExistsError, ProjectNotFoundError
from shared.frontmatter import write
from tools.documents import (
    create_document,
    delete_document,
    list_documents,
    move_document,
    read_document,
    rename_document,
)


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


# ---------------------------------------------------------------------------
# TestCreateDocument
# ---------------------------------------------------------------------------


class TestCreateDocument:
    def test_creates_file_with_frontmatter(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        make_project(tmp_path, "Alpha")

        result = create_document(project_name="Alpha", filename="notes", content="Hi.")

        doc_path = tmp_path / "alpha" / "notes.md"
        assert doc_path.exists()
        text = doc_path.read_text(encoding="utf-8")
        assert text.startswith("---\n")
        assert "Hi." in text
        assert result["doc_path"] == str(doc_path)
        assert result["doc_id"]

    def test_creates_intermediate_directories(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        make_project(tmp_path, "Alpha")

        create_document(project_name="Alpha", filename="notes", subdirectory="q3/reports")

        assert (tmp_path / "alpha" / "q3" / "reports" / "notes.md").exists()

    def test_raises_file_already_exists(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md")

        with pytest.raises(FileAlreadyExistsError):
            create_document(project_name="Alpha", filename="notes")

    def test_raises_project_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)

        with pytest.raises(ProjectNotFoundError):
            create_document(project_name="Nonexistent", filename="notes")


# ---------------------------------------------------------------------------
# TestReadDocument
# ---------------------------------------------------------------------------


class TestReadDocument:
    def test_returns_content_without_frontmatter(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md", doc_id="d1", content="Body only.\n")

        result = read_document(project_name="Alpha", doc_path="notes.md")

        assert result["content"] == "Body only.\n"
        assert result["doc_id"] == "d1"
        assert result["last_modified"] == "2026-01-01T00:00:00+00:00"
        assert result["has_draft"] is False

    def test_has_draft_true_when_draft_exists(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md")
        draft_path = project_dir / ".inkclerk" / "drafts" / "notes.md"
        draft_path.parent.mkdir(parents=True)
        draft_path.write_text("Draft body", encoding="utf-8")

        result = read_document(project_name="Alpha", doc_path="notes.md")
        assert result["has_draft"] is True

    def test_raises_document_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        make_project(tmp_path, "Alpha")

        with pytest.raises(DocumentNotFoundError):
            read_document(project_name="Alpha", doc_path="missing.md")


# ---------------------------------------------------------------------------
# TestListDocuments
# ---------------------------------------------------------------------------


class TestListDocuments:
    def test_lists_all_md_files_with_correct_fields(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md", doc_id="d1")
        make_document(project_dir, "q3/roadmap.md", doc_id="d2")

        results = list_documents(project_name="Alpha")

        assert len(results) == 2
        rel_paths = {r["relative_path"] for r in results}
        assert rel_paths == {"notes.md", "q3/roadmap.md"}
        for r in results:
            assert set(r.keys()) == {
                "doc_path",
                "doc_id",
                "relative_path",
                "last_modified",
                "has_draft",
            }

    def test_excludes_inkclerk_directory(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md")
        draft_path = project_dir / ".inkclerk" / "drafts" / "notes.md"
        draft_path.parent.mkdir(parents=True)
        draft_path.write_text("Draft body", encoding="utf-8")

        results = list_documents(project_name="Alpha")

        assert len(results) == 1
        assert results[0]["relative_path"] == "notes.md"

    def test_has_draft_reflects_existence(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md")
        make_document(project_dir, "other.md")
        draft_path = project_dir / ".inkclerk" / "drafts" / "notes.md"
        draft_path.parent.mkdir(parents=True)
        draft_path.write_text("Draft body", encoding="utf-8")

        results = {r["relative_path"]: r["has_draft"] for r in list_documents(project_name="Alpha")}
        assert results["notes.md"] is True
        assert results["other.md"] is False


# ---------------------------------------------------------------------------
# TestDeleteDocument
# ---------------------------------------------------------------------------


class TestDeleteDocument:
    def test_deletes_formal_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        doc_path = make_document(project_dir, "notes.md")

        delete_document(project_name="Alpha", doc_path="notes.md")

        assert not doc_path.exists()

    def test_deletes_draft_if_exists(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md")
        draft_path = project_dir / ".inkclerk" / "drafts" / "notes.md"
        draft_path.parent.mkdir(parents=True)
        draft_path.write_text("Draft body", encoding="utf-8")

        result = delete_document(project_name="Alpha", doc_path="notes.md")

        assert result["draft_deleted"] is True
        assert not draft_path.exists()

    def test_draft_deleted_false_when_no_draft(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md")

        result = delete_document(project_name="Alpha", doc_path="notes.md")
        assert result["draft_deleted"] is False

    def test_raises_document_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        make_project(tmp_path, "Alpha")

        with pytest.raises(DocumentNotFoundError):
            delete_document(project_name="Alpha", doc_path="missing.md")


# ---------------------------------------------------------------------------
# TestRenameDocument
# ---------------------------------------------------------------------------


class TestRenameDocument:
    def test_renames_file_in_same_directory(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "q3/notes.md")

        result = rename_document(
            project_name="Alpha", doc_path="q3/notes.md", new_filename="q3-notes"
        )

        assert not (project_dir / "q3" / "notes.md").exists()
        assert (project_dir / "q3" / "q3-notes.md").exists()
        assert result["new_doc_path"] == str(project_dir / "q3" / "q3-notes.md")

    def test_moves_draft_if_exists(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md")
        old_draft = project_dir / ".inkclerk" / "drafts" / "notes.md"
        old_draft.parent.mkdir(parents=True)
        old_draft.write_text("Draft body", encoding="utf-8")

        result = rename_document(project_name="Alpha", doc_path="notes.md", new_filename="new-notes")

        assert result["draft_moved"] is True
        assert not old_draft.exists()
        assert (project_dir / ".inkclerk" / "drafts" / "new-notes.md").exists()

    def test_draft_moved_false_when_no_draft(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md")

        result = rename_document(project_name="Alpha", doc_path="notes.md", new_filename="new-notes")
        assert result["draft_moved"] is False

    def test_renames_assets_folder_and_rewrites_references(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(
            project_dir,
            "notes.md",
            content="See ![diagram](./notes-assets/diagram.png) for details.\n",
        )
        assets_dir = project_dir / "notes-assets"
        assets_dir.mkdir()
        (assets_dir / "diagram.png").write_bytes(b"fake-png")

        result = rename_document(project_name="Alpha", doc_path="notes.md", new_filename="new-notes")

        assert result["assets_moved"] is True
        assert not assets_dir.exists()
        new_assets = project_dir / "new-notes-assets"
        assert (new_assets / "diagram.png").exists()

        new_body = (project_dir / "new-notes.md").read_text(encoding="utf-8")
        assert "./new-notes-assets/diagram.png" in new_body
        assert "./notes-assets/" not in new_body

    def test_assets_moved_false_when_no_assets_folder(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md")

        result = rename_document(project_name="Alpha", doc_path="notes.md", new_filename="new-notes")
        assert result["assets_moved"] is False

    def test_updates_last_modified(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md", last_modified="2026-01-01T00:00:00+00:00")

        rename_document(project_name="Alpha", doc_path="notes.md", new_filename="new-notes")

        result = read_document(project_name="Alpha", doc_path="new-notes.md")
        assert result["last_modified"] != "2026-01-01T00:00:00+00:00"

    def test_raises_file_already_exists(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md")
        make_document(project_dir, "other.md")

        with pytest.raises(FileAlreadyExistsError):
            rename_document(project_name="Alpha", doc_path="notes.md", new_filename="other")

    def test_raises_document_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        make_project(tmp_path, "Alpha")

        with pytest.raises(DocumentNotFoundError):
            rename_document(project_name="Alpha", doc_path="missing.md", new_filename="x")


# ---------------------------------------------------------------------------
# TestMoveDocument
# ---------------------------------------------------------------------------


class TestMoveDocument:
    def test_moves_within_same_project(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md")

        result = move_document(
            project_name="Alpha", doc_path="notes.md", destination_path="archive/notes.md"
        )

        assert not (project_dir / "notes.md").exists()
        assert (project_dir / "archive" / "notes.md").exists()
        assert result["new_doc_path"] == str(project_dir / "archive" / "notes.md")

    def test_moves_to_different_project(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        src_dir = make_project(tmp_path, "Alpha")
        dst_dir = make_project(tmp_path, "Beta")
        make_document(src_dir, "notes.md")

        result = move_document(
            project_name="Alpha",
            doc_path="notes.md",
            destination_path="notes.md",
            destination_project_name="Beta",
        )

        assert not (src_dir / "notes.md").exists()
        assert (dst_dir / "notes.md").exists()
        assert result["new_doc_path"] == str(dst_dir / "notes.md")

    def test_moves_draft_if_exists(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md")
        old_draft = project_dir / ".inkclerk" / "drafts" / "notes.md"
        old_draft.parent.mkdir(parents=True)
        old_draft.write_text("Draft body", encoding="utf-8")

        result = move_document(
            project_name="Alpha", doc_path="notes.md", destination_path="archive/notes.md"
        )

        assert result["draft_moved"] is True
        assert not old_draft.exists()
        assert (project_dir / ".inkclerk" / "drafts" / "archive" / "notes.md").exists()

    def test_moves_assets_folder_and_rewrites_references_when_stem_changes(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(
            project_dir,
            "notes.md",
            content="See ![diagram](./notes-assets/diagram.png) for details.\n",
        )
        assets_dir = project_dir / "notes-assets"
        assets_dir.mkdir()
        (assets_dir / "diagram.png").write_bytes(b"fake-png")

        result = move_document(
            project_name="Alpha", doc_path="notes.md", destination_path="archive/new-notes.md"
        )

        assert result["assets_moved"] is True
        assert not assets_dir.exists()
        new_assets = project_dir / "archive" / "new-notes-assets"
        assert (new_assets / "diagram.png").exists()

        new_body = (project_dir / "archive" / "new-notes.md").read_text(encoding="utf-8")
        assert "./new-notes-assets/diagram.png" in new_body

    def test_raises_file_already_exists(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md")
        make_document(project_dir, "archive/notes.md")

        with pytest.raises(FileAlreadyExistsError):
            move_document(
                project_name="Alpha", doc_path="notes.md", destination_path="archive/notes.md"
            )

    def test_rejects_path_traversal(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md")

        with pytest.raises(DocumentNotFoundError):
            move_document(
                project_name="Alpha", doc_path="notes.md", destination_path="../outside.md"
            )

    def test_raises_document_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        make_project(tmp_path, "Alpha")

        with pytest.raises(DocumentNotFoundError):
            move_document(project_name="Alpha", doc_path="missing.md", destination_path="x.md")
