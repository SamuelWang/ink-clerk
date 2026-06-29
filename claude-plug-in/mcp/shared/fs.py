import json
import re
from pathlib import Path

from shared.errors import (
    AmbiguousProjectNameError,
    DocumentNotFoundError,
    ProjectNotFoundError,
)

PROJECTS_ROOT: Path = Path.home() / "Documents" / "InkClerk"


def slugify(name: str) -> str:
    s = name.lower()
    s = re.sub(r"(?:[^\w]|_)+", "-", s)
    return s.strip("-") or "untitled"


def resolve_project(name: str) -> tuple[Path, dict]:
    matches: list[tuple[Path, dict]] = []
    if PROJECTS_ROOT.exists():
        for child in PROJECTS_ROOT.iterdir():
            if not child.is_dir():
                continue
            pj = child / ".inkclerk" / "project.json"
            if not pj.exists():
                continue
            data = json.loads(pj.read_text(encoding="utf-8"))
            if data.get("name", "").lower() == name.lower():
                matches.append((child, data))
    if not matches:
        raise ProjectNotFoundError(f"No project named '{name}' found")
    if len(matches) > 1:
        raise AmbiguousProjectNameError(f"Multiple projects named '{name}'")
    return matches[0]


def resolve_doc(project_path: Path, doc_path: str) -> Path:
    abs_path = (project_path / doc_path).resolve()
    if not abs_path.is_relative_to(project_path.resolve()):
        raise DocumentNotFoundError(
            f"Path '{doc_path}' is outside the project")
    if not abs_path.exists() or not abs_path.is_file():
        raise DocumentNotFoundError(f"Document '{doc_path}' not found")
    return abs_path


def draft_path_for(project_path: Path, rel_path: str) -> Path:
    return project_path / ".inkclerk" / "drafts" / rel_path


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
