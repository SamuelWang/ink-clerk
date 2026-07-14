---
name: propose-edit
description: Propose an AI-generated edit to a document and write it as a draft
argument-hint: "[instruction]"
---

Propose an AI-generated edit to a document and save it as a draft, using the `propose_edit` MCP tool.

InkClerk's core workflow: AI edits land as drafts, the user reviews the diff, and only an explicit accept turns a draft into the formal version. Never write the revised content directly to the formal `.md` file — always go through `propose_edit` so the user can review before accepting.

1. Identify the target document. If the user has a document open or has already given a `project_name`/`doc_path` earlier in the conversation, use that. Otherwise ask the user which project and document (relative path) they mean.

2. Call `read_document(project_name, doc_path)` to fetch the current formal content. If it raises `FILE_NOT_FOUND`, tell the user the document doesn't exist and stop.

3. Determine the editing instruction: use `$ARGUMENTS` if non-empty, otherwise ask the user what change they want made.

4. Generate the full revised Markdown body reflecting the instruction, based on the content returned by `read_document`. Produce the complete new body, not a patch — `propose_edit` takes the full replacement content.

5. Call `propose_edit(project_name, doc_path, content=<revised content>)`. If the result has `overwritten: true`, tell the user: "A previous draft was replaced."

6. Call `get_diff(project_name, doc_path)` and display the result in a fenced ```diff``` code block, along with the `additions`/`deletions` counts.

7. Prompt the user: "Run `/inkclerk:accept-draft` to accept or `/inkclerk:reject-draft` to discard."
