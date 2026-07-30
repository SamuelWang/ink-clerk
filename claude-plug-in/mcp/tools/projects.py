import json
import shutil
from datetime import datetime, timezone

from mcp.types import ToolAnnotations
from uuid_extensions import uuid7

import shared.fs as fs
from shared.mcp_instance import mcp
from shared.errors import FolderAlreadyExistsError
from shared.fs import ensure_dir, resolve_project, slugify


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@mcp.tool()
def create_project(name: str, description: str = "") -> dict:
    slug = slugify(name)
    project_path = fs.PROJECTS_ROOT / slug
    if project_path.exists():
        raise FolderAlreadyExistsError(f"Project folder '{slug}' already exists")

    inkclerk_dir = project_path / ".inkclerk"
    ensure_dir(inkclerk_dir)

    project_id = uuid7(as_type="str")
    now = _now()
    data = {
        "version": 1,
        "id": project_id,
        "name": name,
        "description": description,
        "created": now,
        "lastModified": now,
    }
    project_json_path = inkclerk_dir / "project.json"
    project_json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    return {
        "project_id": project_id,
        "project_path": str(project_path),
        "project_json_path": str(project_json_path),
    }


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
def list_projects() -> list[dict]:
    if not fs.PROJECTS_ROOT.exists():
        return []

    summaries = []
    for child in fs.PROJECTS_ROOT.iterdir():
        if not child.is_dir():
            continue
        pj = child / ".inkclerk" / "project.json"
        if not pj.exists():
            continue
        data = json.loads(pj.read_text(encoding="utf-8"))
        summaries.append(
            {
                "path": str(child),
                "id": data.get("id"),
                "name": data.get("name"),
                "description": data.get("description"),
                "last_modified": data.get("lastModified"),
            }
        )
    return summaries


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
def delete_project(project_name: str) -> dict:
    project_path, data = resolve_project(project_name)
    project_id = data.get("id")
    shutil.rmtree(project_path)
    return {"project_id": project_id, "deleted_path": str(project_path)}


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
def rename_project(project_name: str, new_name: str) -> dict:
    project_path, data = resolve_project(project_name)
    new_slug = slugify(new_name)
    new_path = fs.PROJECTS_ROOT / new_slug
    if new_path.exists():
        raise FolderAlreadyExistsError(f"Project folder '{new_slug}' already exists")

    project_path.rename(new_path)

    data["name"] = new_name
    data["lastModified"] = _now()
    project_json_path = new_path / ".inkclerk" / "project.json"
    project_json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    return {
        "project_id": data.get("id"),
        "old_path": str(project_path),
        "new_path": str(new_path),
        "new_name": new_name,
    }
