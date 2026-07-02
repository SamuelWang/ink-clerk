import json
from pathlib import Path

import pytest

import shared.fs as fs
from shared.errors import (
    AmbiguousProjectNameError,
    FolderAlreadyExistsError,
    ProjectNotFoundError,
)
from tools.projects import (
    create_project,
    delete_project,
    list_projects,
    rename_project,
)


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


# ---------------------------------------------------------------------------
# TestCreateProject
# ---------------------------------------------------------------------------


class TestCreateProject:
    def test_creates_folder_and_project_json(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)

        result = create_project(name="Meeting Notes")

        project_path = tmp_path / "meeting-notes"
        project_json_path = project_path / ".inkclerk" / "project.json"
        assert project_path.is_dir()
        assert project_json_path.exists()
        assert result["project_path"] == str(project_path)
        assert result["project_json_path"] == str(project_json_path)

    def test_project_json_has_correct_schema(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)

        result = create_project(name="Meeting Notes", description="Weekly sync")

        project_json_path = tmp_path / "meeting-notes" / ".inkclerk" / "project.json"
        data = json.loads(project_json_path.read_text(encoding="utf-8"))

        assert data["version"] == 1
        assert data["id"] == result["project_id"]
        assert data["name"] == "Meeting Notes"
        assert data["description"] == "Weekly sync"
        assert "created" in data
        assert "lastModified" in data
        assert data["created"] == data["lastModified"]

    def test_id_is_uuid_string(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        result = create_project(name="Test")
        project_id = result["project_id"]
        assert isinstance(project_id, str)
        assert len(project_id) == 36
        assert project_id.count("-") == 4

    def test_description_defaults_to_empty_string(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        create_project(name="Test")
        data = json.loads(
            (tmp_path / "test" / ".inkclerk" / "project.json").read_text(encoding="utf-8")
        )
        assert data["description"] == ""

    def test_slug_derivation(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        result = create_project(name="Meeting Notes!")
        assert (tmp_path / "meeting-notes").is_dir()
        assert "meeting-notes" in result["project_path"]

    def test_raises_folder_already_exists(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        (tmp_path / "meeting-notes").mkdir()

        with pytest.raises(FolderAlreadyExistsError):
            create_project(name="Meeting Notes")

    def test_returns_correct_output_fields(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        result = create_project(name="Alpha")
        assert set(result.keys()) == {"project_id", "project_path", "project_json_path"}


# ---------------------------------------------------------------------------
# TestListProjects
# ---------------------------------------------------------------------------


class TestListProjects:
    def test_empty_root_returns_empty_list(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        assert list_projects() == []

    def test_nonexistent_root_returns_empty_list(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path / "does-not-exist")
        assert list_projects() == []

    def test_returns_summary_for_each_valid_project(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        make_project(tmp_path, "Alpha", project_id="id-alpha")
        make_project(tmp_path, "Beta", project_id="id-beta")

        results = list_projects()
        assert len(results) == 2
        names = {r["name"] for r in results}
        assert names == {"Alpha", "Beta"}

    def test_summary_fields_are_correct(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Meeting Notes", project_id="uuid-123")

        results = list_projects()
        assert len(results) == 1
        r = results[0]
        assert r["path"] == str(project_dir)
        assert r["id"] == "uuid-123"
        assert r["name"] == "Meeting Notes"
        assert r["description"] == "A test project"
        assert r["last_modified"] == "2026-01-01T00:00:00+00:00"

    def test_directories_without_project_json_are_ignored(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        (tmp_path / "random-folder").mkdir()
        make_project(tmp_path, "Real Project")

        results = list_projects()
        assert len(results) == 1
        assert results[0]["name"] == "Real Project"

    def test_files_in_root_are_ignored(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        (tmp_path / "stray-file.txt").write_text("hi", encoding="utf-8")
        make_project(tmp_path, "My Project")

        results = list_projects()
        assert len(results) == 1


# ---------------------------------------------------------------------------
# TestDeleteProject
# ---------------------------------------------------------------------------


class TestDeleteProject:
    def test_deletes_project_directory(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha", project_id="id-alpha")

        delete_project(project_name="Alpha")

        assert not project_dir.exists()

    def test_returns_project_id_and_deleted_path(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Alpha", project_id="id-alpha")

        result = delete_project(project_name="Alpha")

        assert result["project_id"] == "id-alpha"
        assert result["deleted_path"] == str(project_dir)

    def test_raises_project_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)

        with pytest.raises(ProjectNotFoundError):
            delete_project(project_name="Nonexistent")

    def test_raises_ambiguous_project_name(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        for slug in ("alpha-a", "alpha-b"):
            d = tmp_path / slug / ".inkclerk"
            d.mkdir(parents=True)
            (d / "project.json").write_text(
                json.dumps({"version": 1, "id": slug, "name": "Alpha", "description": ""}),
                encoding="utf-8",
            )

        with pytest.raises(AmbiguousProjectNameError):
            delete_project(project_name="Alpha")

    def test_case_insensitive_match(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        project_dir = make_project(tmp_path, "Meeting Notes")

        delete_project(project_name="meeting notes")

        assert not project_dir.exists()


# ---------------------------------------------------------------------------
# TestRenameProject
# ---------------------------------------------------------------------------


class TestRenameProject:
    def test_renames_project_folder(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        old_dir = make_project(tmp_path, "Alpha")

        rename_project(project_name="Alpha", new_name="Beta")

        assert not old_dir.exists()
        assert (tmp_path / "beta").is_dir()

    def test_updates_name_and_last_modified_in_project_json(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        make_project(tmp_path, "Alpha", project_id="id-alpha")

        rename_project(project_name="Alpha", new_name="Beta")

        data = json.loads(
            (tmp_path / "beta" / ".inkclerk" / "project.json").read_text(encoding="utf-8")
        )
        assert data["name"] == "Beta"
        assert data["lastModified"] != "2026-01-01T00:00:00+00:00"

    def test_preserves_id_and_created_in_project_json(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        make_project(tmp_path, "Alpha", project_id="id-alpha")

        rename_project(project_name="Alpha", new_name="Beta")

        data = json.loads(
            (tmp_path / "beta" / ".inkclerk" / "project.json").read_text(encoding="utf-8")
        )
        assert data["id"] == "id-alpha"
        assert data["created"] == "2026-01-01T00:00:00+00:00"

    def test_returns_correct_output_fields(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        old_dir = make_project(tmp_path, "Alpha", project_id="id-alpha")

        result = rename_project(project_name="Alpha", new_name="Beta")

        assert result["project_id"] == "id-alpha"
        assert result["old_path"] == str(old_dir)
        assert result["new_path"] == str(tmp_path / "beta")
        assert result["new_name"] == "Beta"

    def test_raises_folder_already_exists(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        make_project(tmp_path, "Alpha")
        make_project(tmp_path, "Beta")

        with pytest.raises(FolderAlreadyExistsError):
            rename_project(project_name="Alpha", new_name="Beta")

    def test_raises_project_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)

        with pytest.raises(ProjectNotFoundError):
            rename_project(project_name="Nonexistent", new_name="Other")

    def test_raises_ambiguous_project_name(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        for slug in ("alpha-a", "alpha-b"):
            d = tmp_path / slug / ".inkclerk"
            d.mkdir(parents=True)
            (d / "project.json").write_text(
                json.dumps({"version": 1, "id": slug, "name": "Alpha", "description": ""}),
                encoding="utf-8",
            )

        with pytest.raises(AmbiguousProjectNameError):
            rename_project(project_name="Alpha", new_name="Beta")

    def test_case_insensitive_match(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fs, "PROJECTS_ROOT", tmp_path)
        make_project(tmp_path, "Meeting Notes")

        rename_project(project_name="meeting notes", new_name="Team Syncs")

        assert (tmp_path / "team-syncs").is_dir()
