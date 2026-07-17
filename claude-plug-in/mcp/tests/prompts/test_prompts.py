import json
from pathlib import Path

import pytest

import prompts.prompts as prompts
import shared.fs as fs
from shared.errors import NoDraftError
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
# TestEditDocumentPrompt
# ---------------------------------------------------------------------------


class TestEditDocumentPrompt:
    def test_messages_carry_contract_and_content_and_instruction(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md", content="# Title\n\nOriginal body.\n")

        result = prompts.edit_document("Alpha", "notes.md", "Make it more formal")

        assert len(result) == 2
        assert result[0].role == "user"
        assert "draft" in result[0].content.text.lower()
        assert result[1].role == "user"
        assert "Original body." in result[1].content.text
        assert "Make it more formal" in result[1].content.text


# ---------------------------------------------------------------------------
# TestCreateDocumentPrompt
# ---------------------------------------------------------------------------


class TestCreateDocumentPrompt:
    def test_messages_carry_brief_and_project_context(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "existing.md")

        result = prompts.create_document("Alpha", "A meeting agenda for the Q3 planning sync")

        assert len(result) == 2
        combined = "\n".join(m.content.text for m in result)
        assert "A meeting agenda for the Q3 planning sync" in combined
        assert "Alpha" in combined
        assert "A test project" in combined
        assert "existing.md" in combined


# ---------------------------------------------------------------------------
# TestImportGoogleDocPrompt
# ---------------------------------------------------------------------------


class TestImportGoogleDocPrompt:
    def test_messages_carry_project_name(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)

        result = prompts.import_google_doc("Alpha")

        combined = "\n".join(m.content.text for m in result)
        assert "Alpha" in combined

    def test_optional_filename_and_subdirectory_included_when_given(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)

        result = prompts.import_google_doc(
            "Alpha",
            filename="meeting-notes",
            subdirectory="notes",
        )

        combined = "\n".join(m.content.text for m in result)
        assert "meeting-notes" in combined
        assert "notes" in combined

    def test_optional_args_omitted_when_not_given(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)

        result = prompts.import_google_doc("Alpha")

        combined = "\n".join(m.content.text for m in result)
        assert "Filename:" not in combined
        assert "Subdirectory:" not in combined


# ---------------------------------------------------------------------------
# TestAcceptDraftPrompt
# ---------------------------------------------------------------------------


class TestAcceptDraftPrompt:
    def test_messages_carry_diff_and_confirmation_question(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md", content="Original.\n")
        make_draft(project_dir, "notes.md", content="Revised.\n")

        result = prompts.accept_draft("Alpha", "notes.md")

        combined = "\n".join(m.content.text for m in result)
        assert "Original" in combined or "-Original" in combined
        assert "Revised" in combined or "+Revised" in combined
        assert "Accept this draft? This will overwrite the formal document. (yes/no)" in combined

    def test_raises_no_draft_error_when_no_draft_exists(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha")
        make_document(project_dir, "notes.md")

        with pytest.raises(NoDraftError):
            prompts.accept_draft("Alpha", "notes.md")
