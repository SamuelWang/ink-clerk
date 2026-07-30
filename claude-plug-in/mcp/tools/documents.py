import shutil
from datetime import datetime, timezone
from pathlib import Path

from mcp.types import ToolAnnotations
from uuid_extensions import uuid7

from shared.mcp_instance import mcp
from shared.errors import DocumentNotFoundError, FileAlreadyExistsError
from shared.fs import draft_path_for, ensure_dir, resolve_doc, resolve_project
from shared.frontmatter import parse, write


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@mcp.tool()
def create_document(
    project_name: str, filename: str, subdirectory: str = "", content: str = ""
) -> dict:
    project_path, _ = resolve_project(project_name)
    doc_path = project_path / subdirectory / f"{filename}.md"
    if doc_path.exists():
        raise FileAlreadyExistsError(f"Document '{filename}.md' already exists")

    ensure_dir(doc_path.parent)

    doc_id = uuid7(as_type="str")
    now = _now()
    meta = {"id": doc_id, "created": now, "lastModified": now}
    doc_path.write_text(write(meta, content), encoding="utf-8")

    return {"doc_path": str(doc_path), "doc_id": doc_id}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
def read_document(project_name: str, doc_path: str) -> dict:
    project_path, _ = resolve_project(project_name)
    abs_path = resolve_doc(project_path, doc_path)

    text = abs_path.read_text(encoding="utf-8")
    meta, body = parse(text)

    return {
        "content": body,
        "doc_id": meta.get("id"),
        "last_modified": meta.get("lastModified"),
        "has_draft": draft_path_for(project_path, doc_path).exists(),
    }


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
def list_documents(project_name: str) -> list[dict]:
    project_path, _ = resolve_project(project_name)

    summaries = []
    for md_path in sorted(project_path.rglob("*.md")):
        rel_path = md_path.relative_to(project_path)
        if ".inkclerk" in rel_path.parts:
            continue

        text = md_path.read_text(encoding="utf-8")
        meta, _ = parse(text)
        summaries.append(
            {
                "doc_path": str(md_path),
                "doc_id": meta.get("id"),
                "relative_path": str(rel_path),
                "last_modified": meta.get("lastModified"),
                "has_draft": draft_path_for(project_path, str(rel_path)).exists(),
            }
        )
    return summaries


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
def delete_document(project_name: str, doc_path: str) -> dict:
    project_path, _ = resolve_project(project_name)
    abs_path = resolve_doc(project_path, doc_path)
    abs_path.unlink()

    draft = draft_path_for(project_path, doc_path)
    draft_deleted = draft.exists()
    if draft_deleted:
        draft.unlink()

    return {"draft_deleted": draft_deleted}


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
def rename_document(project_name: str, doc_path: str, new_filename: str) -> dict:
    project_path, _ = resolve_project(project_name)
    old_abs = resolve_doc(project_path, doc_path)
    old_stem = old_abs.stem
    new_abs = old_abs.with_name(f"{new_filename}.md")

    if new_abs.exists():
        raise FileAlreadyExistsError(f"Document '{new_abs.name}' already exists")

    new_rel = str(Path(doc_path).with_name(f"{new_filename}.md"))

    old_abs.rename(new_abs)

    draft_moved = False
    old_draft = draft_path_for(project_path, doc_path)
    if old_draft.exists():
        new_draft = draft_path_for(project_path, new_rel)
        ensure_dir(new_draft.parent)
        old_draft.rename(new_draft)
        draft_moved = True

    assets_moved = False
    old_assets = old_abs.with_name(f"{old_stem}-assets")
    if old_assets.exists():
        new_assets = new_abs.with_name(f"{new_filename}-assets")
        old_assets.rename(new_assets)
        assets_moved = True

    text = new_abs.read_text(encoding="utf-8")
    meta, body = parse(text)
    if assets_moved:
        body = body.replace(f"./{old_stem}-assets/", f"./{new_filename}-assets/")
    meta["lastModified"] = _now()
    new_abs.write_text(write(meta, body), encoding="utf-8")

    return {
        "old_doc_path": str(old_abs),
        "new_doc_path": str(new_abs),
        "draft_moved": draft_moved,
        "assets_moved": assets_moved,
    }


@mcp.tool()
def move_document(
    project_name: str,
    doc_path: str,
    destination_path: str,
    destination_project_name: str = "",
) -> dict:
    src_project_path, _ = resolve_project(project_name)
    old_abs = resolve_doc(src_project_path, doc_path)
    old_stem = old_abs.stem

    if destination_project_name:
        dst_project_path, _ = resolve_project(destination_project_name)
    else:
        dst_project_path = src_project_path

    dst_root = dst_project_path.resolve()
    new_abs = (dst_project_path / destination_path).resolve()
    if not new_abs.is_relative_to(dst_root):
        raise DocumentNotFoundError(
            f"Destination '{destination_path}' is outside the project"
        )
    if new_abs.exists():
        raise FileAlreadyExistsError(f"Document '{destination_path}' already exists")

    new_stem = new_abs.stem

    ensure_dir(new_abs.parent)
    shutil.move(str(old_abs), str(new_abs))

    draft_moved = False
    old_draft = draft_path_for(src_project_path, doc_path)
    if old_draft.exists():
        new_draft = draft_path_for(dst_project_path, destination_path)
        ensure_dir(new_draft.parent)
        shutil.move(str(old_draft), str(new_draft))
        draft_moved = True

    assets_moved = False
    old_assets = old_abs.with_name(f"{old_stem}-assets")
    if old_assets.exists():
        new_assets = new_abs.with_name(f"{new_stem}-assets")
        ensure_dir(new_assets.parent)
        shutil.move(str(old_assets), str(new_assets))
        assets_moved = True

    text = new_abs.read_text(encoding="utf-8")
    meta, body = parse(text)
    if assets_moved and old_stem != new_stem:
        body = body.replace(f"./{old_stem}-assets/", f"./{new_stem}-assets/")
    meta["lastModified"] = _now()
    new_abs.write_text(write(meta, body), encoding="utf-8")

    return {
        "old_doc_path": str(old_abs),
        "new_doc_path": str(new_abs),
        "draft_moved": draft_moved,
        "assets_moved": assets_moved,
    }
