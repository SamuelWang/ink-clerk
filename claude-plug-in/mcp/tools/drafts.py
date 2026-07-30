import difflib
from datetime import datetime, timezone

from mcp.types import ToolAnnotations

from shared.mcp_instance import mcp
from shared.errors import NoDraftError
from shared.fs import draft_path_for, ensure_dir, resolve_doc, resolve_project
from shared.frontmatter import parse, write


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@mcp.tool()
def propose_edit(project_name: str, doc_path: str, content: str) -> dict:
    project_path, _ = resolve_project(project_name)
    resolve_doc(project_path, doc_path)

    draft = draft_path_for(project_path, doc_path)
    overwritten = draft.exists()

    ensure_dir(draft.parent)
    draft.write_text(content, encoding="utf-8")

    return {"draft_path": str(draft), "overwritten": overwritten}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
def get_draft(project_name: str, doc_path: str) -> dict:
    project_path, _ = resolve_project(project_name)
    resolve_doc(project_path, doc_path)

    draft = draft_path_for(project_path, doc_path)
    if not draft.exists():
        raise NoDraftError(f"No draft exists for '{doc_path}'")

    return {"content": draft.read_text(encoding="utf-8"), "draft_path": str(draft)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
def get_diff(project_name: str, doc_path: str) -> dict:
    project_path, _ = resolve_project(project_name)
    abs_path = resolve_doc(project_path, doc_path)

    draft = draft_path_for(project_path, doc_path)
    if not draft.exists():
        raise NoDraftError(f"No draft exists for '{doc_path}'")

    formal_text = abs_path.read_text(encoding="utf-8")
    _, formal_body = parse(formal_text)
    draft_content = draft.read_text(encoding="utf-8")

    diff_lines = list(
        difflib.unified_diff(
            formal_body.splitlines(keepends=True),
            draft_content.splitlines(keepends=True),
            fromfile="formal",
            tofile="draft",
        )
    )
    diff_str = "".join(diff_lines)
    additions = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
    deletions = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))

    return {"diff": diff_str, "additions": additions, "deletions": deletions}


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
def accept_draft(project_name: str, doc_path: str) -> dict:
    project_path, _ = resolve_project(project_name)
    abs_path = resolve_doc(project_path, doc_path)

    draft = draft_path_for(project_path, doc_path)
    if not draft.exists():
        raise NoDraftError(f"No draft exists for '{doc_path}'")

    meta, _ = parse(abs_path.read_text(encoding="utf-8"))
    draft_content = draft.read_text(encoding="utf-8")

    meta["lastModified"] = _now()
    abs_path.write_text(write(meta, draft_content), encoding="utf-8")
    draft.unlink()

    return {"doc_path": str(abs_path)}


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
def reject_draft(project_name: str, doc_path: str) -> dict:
    project_path, _ = resolve_project(project_name)
    resolve_doc(project_path, doc_path)

    draft = draft_path_for(project_path, doc_path)
    if not draft.exists():
        raise NoDraftError(f"No draft exists for '{doc_path}'")

    draft.unlink()
    return {"draft_path": str(draft)}
