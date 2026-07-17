---
name: import-google-doc
description: Import a Google Doc into an InkClerk project as a Markdown document
argument-hint: "[project-name] [filename]"
---

Import a Google Doc into an InkClerk project as a new Markdown document, using the `import_google_doc` MCP tool.

InkClerk's core workflow: AI edits land as drafts, the user reviews the diff, and only an explicit accept turns a draft into the formal version. A freshly imported document has no draft — it is created directly as the formal version, since there is nothing yet to diff it against.

1. Parse `$ARGUMENTS` for up to two optional positional values, in order: the target project name and an output filename. There is no URL/ID to collect — the tool always opens a browser window where the user signs in with Google and picks the document via Google's own Picker, so the specific document is never something you ask for or pass in.

2. If the project name is missing, ask the user for it. If they're unsure which project to use, call `list_projects()` and show them the available projects (`name`, `description`, `path`) to choose from.

3. If no filename was given, leave it blank — `import_google_doc` defaults to a slugified version of the Google Doc's title. Only ask about a subdirectory if the user mentions wanting the document nested somewhere inside the project.

4. Call `import_google_doc(project_name=<project_name>, filename=<filename or "">, subdirectory=<subdirectory or "">)`. Let the user know this opens a browser window for Google sign-in and document picking.

5. Handle errors:
   - `AUTH_REQUIRED`: the browser sign-in + Picker round didn't complete (missing configuration, it timed out, or the session expired before the user finished). Tell the user to complete it in their browser and retry the same call.
   - `PROJECT_NOT_FOUND` / `AMBIGUOUS_PROJECT_NAME`: ask the user to clarify the project name, optionally showing `list_projects()` output.
   - `FILE_ALREADY_EXISTS`: ask the user for a different filename, or confirm they want to pick a new one.
   - `PERMISSION_DENIED` / `GOOGLE_API_ERROR`: report the error message and ask the user to check their access to the Google Doc.

6. On success, report the created document's `doc_path`. If the returned `dropped_styles` list is non-empty, list them as styles that could not be preserved; otherwise no need to mention it.
