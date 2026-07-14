---
name: accept-draft
description: Accept the pending draft, making it the formal version of the document
argument-hint: "[doc-path]"
---

Accept the pending draft for a document, making it the formal version, using the `accept_draft` MCP tool.

InkClerk's core workflow: AI edits land as drafts, the user reviews the diff, and only an explicit accept turns a draft into the formal version. This skill performs that explicit accept step — never skip the confirmation in step 3.

1. Identify the target document. If `$ARGUMENTS` contains a doc path, use it together with the current project context. Otherwise use the document the user has open, or ask for the `project_name` and `doc_path`.

2. Call `get_diff(project_name, doc_path)` and display the diff (in a fenced ```diff``` block) for final review, along with `additions`/`deletions` counts. If it raises `NO_DRAFT`, tell the user there is no pending draft for this document and stop — there is nothing to accept.

3. Ask the user: "Accept this draft? This will overwrite the formal document. (yes/no)"

4. If the user confirms (yes): call `accept_draft(project_name, doc_path)`, then report: "Draft accepted. The formal document has been updated."

5. If the user declines (no): report: "Cancelled. The draft was not accepted." Leave the draft in place — do not call `reject_draft`.
