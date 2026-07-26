---
name: reject-draft
description: Discard the pending draft without modifying the formal document
argument-hint: "[doc-path]"
---

Discard the pending draft for a document without touching the formal version, using the `reject_draft` MCP tool.

InkClerk's core workflow: AI edits land as drafts, the user reviews the diff, and only an explicit accept turns a draft into the formal version. Rejecting a draft simply removes the proposed changes — the formal document is never modified by this skill.

1. Identify the target document. If `$ARGUMENTS` contains a doc path, use it together with the current project context. Otherwise use the document the user has open, or ask for the `project_name` and `doc_path`.

2. Call `get_draft(project_name, doc_path)` to confirm a draft exists, and show the user its content (or a summary of it) so they know what will be discarded. If it raises `NO_DRAFT`, tell the user there is no pending draft for this document and stop — there is nothing to discard.

3. Ask the user: "Discard this draft? The formal document will remain unchanged. (yes/no)"

4. If the user confirms (yes): call `reject_draft(project_name, doc_path)`, then report: "Draft discarded. The formal document was not changed."

5. If the user declines (no): report: "Cancelled. The draft was not discarded."
