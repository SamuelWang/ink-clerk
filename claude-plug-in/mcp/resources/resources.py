import json
import urllib.parse

import shared.fs as fs
import tools.documents
import tools.drafts
import tools.projects
from shared.mcp_instance import mcp
from shared.errors import InkClerkError


def _list_projects() -> list[dict]:
    return tools.projects.list_projects()


def _get_project(name: str) -> dict:
    _, data = fs.resolve_project(name)
    return {
        "id": data.get("id"),
        "name": data.get("name"),
        "description": data.get("description"),
        "created": data.get("created"),
        "last_modified": data.get("lastModified"),
        "documents": tools.documents.list_documents(name),
    }


def _get_document(project: str, path: str) -> dict:
    return tools.documents.read_document(project, path)


def _get_draft(project: str, path: str) -> dict:
    return tools.drafts.get_draft(project, path)


# mcp==1.28.0 doesn't support RFC6570 "{+uri}" reserved-expansion (template
# param regex is \w+, can't match the leading "+"); use a plain "{uri}" param
# and re-prepend the scheme, since the SDK strips it before calling this fn.
@mcp.resource("inkclerk://{uri}", mime_type="application/json")
def dispatch(uri: str) -> str:
    parsed = urllib.parse.urlparse(f"inkclerk://{uri}")
    params = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}
    try:
        match parsed.netloc:
            case "projects":
                return json.dumps(_list_projects())
            case "project":
                return json.dumps(_get_project(params["name"]))
            case "document":
                return json.dumps(_get_document(params["project"], params["path"]))
            case "draft":
                return json.dumps(_get_draft(params["project"], params["path"]))
            case _:
                raise ValueError(f"Unknown resource URI: inkclerk://{uri}")
    except InkClerkError as e:
        return json.dumps(e.to_dict())
