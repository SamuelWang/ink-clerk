import json
from pathlib import Path

import pytest

import shared.fs as fs
from shared.errors import (
    AmbiguousProjectNameError,
    DocumentNotFoundError,
    ProjectNotFoundError,
)
from shared.fs import (
    draft_path_for,
    ensure_dir,
    resolve_doc,
    resolve_project,
    slugify,
    truncate_basename,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_project(root: Path, name: str) -> Path:
    slug = name.lower().replace(" ", "-")
    project_dir = root / slug
    inkclerk_dir = project_dir / ".inkclerk"
    inkclerk_dir.mkdir(parents=True)
    (inkclerk_dir / "project.json").write_text(
        json.dumps({"name": name, "id": "test-id"}), encoding="utf-8"
    )
    return project_dir


# ---------------------------------------------------------------------------
# slugify
# ---------------------------------------------------------------------------


class TestSlugify:
    def test_basic_title_case(self):
        assert slugify("Meeting Notes") == "meeting-notes"

    def test_trailing_punctuation(self):
        assert slugify("Meeting Notes!") == "meeting-notes"

    def test_leading_trailing_hyphens_stripped(self):
        assert slugify("  --hello--  ") == "hello"

    def test_non_ascii_letters_preserved(self):
        assert slugify("café Notes") == "café-notes"

    def test_idempotent(self):
        s = "Meeting Notes!"
        assert slugify(slugify(s)) == slugify(s)

    def test_already_slugified_unchanged(self):
        s = "meeting-notes"
        assert slugify(s) == s

    def test_underscores_become_hyphens(self):
        assert slugify("hello_world") == "hello-world"

    def test_multiple_spaces_collapse(self):
        assert slugify("a   b") == "a-b"

    def test_special_chars_only_returns_untitled(self):
        assert slugify("!@#$") == "untitled"


# ---------------------------------------------------------------------------
# resolve_project
# ---------------------------------------------------------------------------


class TestResolveProject:
    def test_single_match_returns_path_and_dict(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Meeting Notes")

        path, data = resolve_project("Meeting Notes")

        assert path == project_dir
        assert data["name"] == "Meeting Notes"
        assert data["id"] == "test-id"

    def test_no_match_raises_project_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        make_project(tmp_path, "Other Project")

        with pytest.raises(ProjectNotFoundError):
            resolve_project("Missing Project")

    def test_two_projects_same_name_raises_ambiguous(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        # Create two dirs with the same project name in their project.json
        for slug in ("meeting-notes-a", "meeting-notes-b"):
            d = tmp_path / slug / ".inkclerk"
            d.mkdir(parents=True)
            (d / "project.json").write_text(
                json.dumps({"name": "Meeting Notes", "id": slug}), encoding="utf-8"
            )

        with pytest.raises(AmbiguousProjectNameError):
            resolve_project("Meeting Notes")

    def test_case_insensitive_match(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        make_project(tmp_path, "Meeting Notes")

        path, data = resolve_project("meeting notes")

        assert data["name"] == "Meeting Notes"

    def test_directory_without_project_json_ignored(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        (tmp_path / "random-folder").mkdir()  # no .inkclerk/project.json
        make_project(tmp_path, "Real Project")

        path, data = resolve_project("Real Project")
        assert data["name"] == "Real Project"

    def test_empty_projects_root_raises_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        with pytest.raises(ProjectNotFoundError):
            resolve_project("Anything")

    def test_nonexistent_projects_root_raises_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path / "does-not-exist")
        with pytest.raises(ProjectNotFoundError):
            resolve_project("Anything")


# ---------------------------------------------------------------------------
# resolve_doc
# ---------------------------------------------------------------------------


class TestResolveDoc:
    def test_valid_path_returns_resolved_path(self, tmp_path):
        doc = tmp_path / "notes.md"
        doc.write_text("# Hello", encoding="utf-8")

        result = resolve_doc(tmp_path, "notes.md")
        assert result == doc.resolve()

    def test_path_traversal_raises_document_not_found(self, tmp_path):
        outside = tmp_path.parent / "secret.md"
        outside.write_text("secret", encoding="utf-8")

        with pytest.raises(DocumentNotFoundError):
            resolve_doc(tmp_path, "../secret.md")

    def test_nonexistent_file_raises_document_not_found(self, tmp_path):
        with pytest.raises(DocumentNotFoundError):
            resolve_doc(tmp_path, "missing.md")

    def test_nested_valid_path(self, tmp_path):
        (tmp_path / "sub").mkdir()
        doc = tmp_path / "sub" / "note.md"
        doc.write_text("content", encoding="utf-8")

        result = resolve_doc(tmp_path, "sub/note.md")
        assert result == doc.resolve()


# ---------------------------------------------------------------------------
# draft_path_for
# ---------------------------------------------------------------------------


class TestDraftPathFor:
    def test_returns_correct_path(self, tmp_path):
        result = draft_path_for(tmp_path, "notes.md")
        assert result == tmp_path / ".inkclerk" / "drafts" / "notes.md"

    def test_nested_rel_path(self, tmp_path):
        result = draft_path_for(tmp_path, "sub/dir/note.md")
        assert result == tmp_path / ".inkclerk" / "drafts" / "sub" / "dir" / "note.md"

    def test_does_not_check_existence(self, tmp_path):
        result = draft_path_for(tmp_path, "nonexistent.md")
        assert not result.exists()


# ---------------------------------------------------------------------------
# ensure_dir
# ---------------------------------------------------------------------------


class TestEnsureDir:
    def test_creates_nested_directories(self, tmp_path):
        target = tmp_path / "a" / "b" / "c"
        assert not target.exists()

        ensure_dir(target)

        assert target.is_dir()

    def test_idempotent_no_error_on_existing(self, tmp_path):
        target = tmp_path / "existing"
        target.mkdir()

        ensure_dir(target)  # must not raise

        assert target.is_dir()


# ---------------------------------------------------------------------------
# truncate_basename
# ---------------------------------------------------------------------------


class TestTruncateBasename:
    def test_short_name_unchanged(self):
        assert truncate_basename("photo.png") == "photo.png"

    def test_ascii_name_over_255_bytes_truncated_with_extension_preserved(self):
        name = ("a" * 300) + ".png"
        result = truncate_basename(name)

        assert len(result.encode("utf-8")) <= 255
        assert result.endswith(".png")

    def test_cjk_name_truncated_without_splitting_multibyte_char(self):
        name = ("會" * 200) + ".png"
        result = truncate_basename(name)

        encoded = result.encode("utf-8")
        assert len(encoded) <= 255
        assert encoded.decode("utf-8") == result
        assert result.endswith(".png")

    def test_preserves_arbitrary_extension(self):
        name = ("a" * 300) + ".jpeg"
        result = truncate_basename(name)

        assert result.endswith(".jpeg")
        assert len(result.encode("utf-8")) <= 255
