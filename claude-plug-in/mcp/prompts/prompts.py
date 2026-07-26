from mcp.server.fastmcp.prompts.base import Message, UserMessage

import shared.fs as fs
import tools.documents
import tools.drafts
from main import mcp

# The installed SDK (mcp==1.28.0) only supports role: Literal["user", "assistant"]
# on prompt messages — there is no "system" role. The contract-establishing
# message described by the execution plan is therefore sent as the first
# UserMessage rather than a true system message.
CONTRACT_MESSAGE = (
    "InkClerk's core workflow: AI edits land as drafts, the user reviews the diff, "
    "and only an explicit accept turns a draft into the formal version. Never modify "
    "the formal .md file directly — always use propose_edit (or create_document for "
    "brand-new files) so the user can review before accepting."
)


@mcp.prompt()
def edit_document(project_name: str, doc_path: str, instruction: str) -> list[Message]:
    doc = tools.documents.read_document(project_name, doc_path)
    task = (
        f"Document content:\n\n{doc['content']}\n\n"
        f"Instruction: {instruction}\n\n"
        "Generate the revised document body reflecting the instruction, then call "
        f'propose_edit(project_name="{project_name}", doc_path="{doc_path}", '
        "content=<revised content>) to save it as a draft."
    )
    return [UserMessage(CONTRACT_MESSAGE), UserMessage(task)]


@mcp.prompt()
def create_document(project_name: str, brief: str) -> list[Message]:
    _, data = fs.resolve_project(project_name)
    docs = tools.documents.list_documents(project_name)
    doc_list = ", ".join(d["relative_path"] for d in docs) or "(none yet)"
    task = (
        f"Project: {data.get('name')} — {data.get('description')}\n"
        f"Existing documents: {doc_list}\n\n"
        f"Brief: {brief}\n\n"
        "Generate a new Markdown document body satisfying the brief, then call "
        f'create_document(project_name="{project_name}", filename=<slug>, '
        "content=<generated content>) to create it."
    )
    return [UserMessage(CONTRACT_MESSAGE), UserMessage(task)]


@mcp.prompt()
def import_google_doc(
    project_name: str, filename: str = "", subdirectory: str = ""
) -> list[Message]:
    lines = [f"Target project: {project_name}"]
    if filename:
        lines.append(f"Filename: {filename}")
    if subdirectory:
        lines.append(f"Subdirectory: {subdirectory}")
    lines.append("")
    lines.append(
        "Call import_google_doc with these parameters to import it. This opens a "
        "browser window for the user to sign in with Google and pick the document "
        "via the Google Picker."
    )
    task = "\n".join(lines)
    return [UserMessage(CONTRACT_MESSAGE), UserMessage(task)]


@mcp.prompt()
def accept_draft(project_name: str, doc_path: str) -> list[Message]:
    result = tools.drafts.get_diff(project_name, doc_path)
    task = (
        f"Diff for {doc_path} ({result['additions']} additions, "
        f"{result['deletions']} deletions):\n\n"
        f"```diff\n{result['diff']}\n```\n\n"
        "Accept this draft? This will overwrite the formal document. (yes/no)"
    )
    return [UserMessage(CONTRACT_MESSAGE), UserMessage(task)]
