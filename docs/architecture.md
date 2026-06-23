# Architecture

## 1. Overview

InkClerk is an AI-first clerical work platform. It provides different apps for managing projects and documents. The apps include but is not limited to Claude Plug-in (MCP Servers and Skills), Desktop App, and Web App.

The core UX contract: `AI edits land as drafts → user reviews diff → user accepts → draft becomes formal version`. This workflow is implemented once in packages/editor and used by both the desktop and web apps.

## 2. Repository Structure

This is a monorepo, the different apps are all in this repo.

### 2.1 Folder Structure

```
ink-clerk/
├── apps/
│   ├── desktop/                    # Tauri v2 + React
│   │   ├── src/                    # React renderer (Vite)
│   │   │   ├── components/
│   │   │   │   ├── editor/         # TipTap wrapper, draft overlay, toolbar
│   │   │   │   ├── sidebar/        # project/file tree
│   │   │   │   └── shell/          # window layout
│   │   │   ├── hooks/              # useFile, useDraft, useEditor → invoke()
│   │   │   └── main.tsx
│   │   ├── src-tauri/              # Rust backend (Cargo, not pnpm)
│   │   │   ├── src/
│   │   │   │   ├── main.rs
│   │   │   │   ├── commands/       # file_read, file_write, draft_accept, project_list, ...
│   │   │   │   └── lib.rs
│   │   │   ├── Cargo.toml
│   │   │   └── tauri.conf.json
│   │   ├── vite.config.ts
│   │   └── package.json
│   ├── web/                        # React SPA
│   │   ├── src/
│   │   │   ├── components/         # Uses @inkclerk/editor and @inkclerk/ui
│   │   │   └── main.tsx
│   │   ├── vite.config.ts
│   │   └── package.json            # "@inkclerk/editor": "workspace:*"
│   └── web-api/                    # FastAPI backend
│       ├── src/
│       │   ├── main.py             # FastAPI app entry
│       │   ├── routers/            # /projects, /files, /drafts, /ai endpoints
│       │   └── services/
│       │       └── ai.py           # anthropic Python SDK calls
│       ├── pyproject.toml          # Python deps: fastapi, anthropic, uvicorn, asyncpg
│       └── uv.lock
├── claude-plug-in/                 # Claude Plug-in (MCP Servers + Claude Code skills)
│   ├── mcp/                        # MCP server — tools, resources, and prompts (Python)
│   │   ├── src/
│   │   └── pyproject.toml
│   └── skills/                     # Claude Code skill definitions (.md)
├── packages/
│   ├── editor/                     # TipTap logic — shared by apps/desktop + apps/web
│   │   ├── src/
│   │   │   ├── extensions/         # DraftAddition, DraftDeletion marks; AIAssist
│   │   │   ├── serializers/        # ProseMirror ↔ markdown (tiptap-markdown)
│   │   │   └── diff.ts             # diff-match-patch: formal ↔ draft text
│   │   └── package.json
│   ├── ui/                         # Shared React components — shared by apps/desktop + apps/web
│   │   ├── src/
│   │   │   └── components/         # Sidebar, Toolbar, Dialog, DiffOverlay
│   │   └── package.json
│   └── ai/                         # BYOK AI client — provider-agnostic LLM adapter for apps/desktop
│       ├── src/
│       │   ├── client.ts           # unified chat interface (stream, complete) over any provider
│       │   └── providers/          # per-provider adapters (Anthropic, OpenAI-compatible, etc.)
│       └── package.json
├── Makefile                        # Cross-language dev orchestration
├── turbo.json                      # JS-only pipeline
├── pnpm-workspace.yaml
├── package.json                    # root devDeps: turbo, typescript
└── tsconfig.base.json
```

## App Directory Layout

### Default projects root

On first launch, InkClerk defaults to `~/Documents/InkClerk/`. The user can change this in settings; the configured value is persisted in the app data.

### Project folder structure

Each project lives as a named subfolder (slugified from the project name). Markdown files may be nested arbitrarily in subdirectories within a project. Asset folders are always siblings of their paired `.md` file, at whatever depth it lives.

```
~/Documents/InkClerk/
├── meeting-notes/
│   ├── .inkclerk/
│   │   └── project.json
│   ├── 2026-06-kickoff.md
│   ├── 2026-06-kickoff-assets/
│   │   ├── diagram.png
│   │   └── screenshot.jpg
│   ├── 2026-06-standup.md          ← no assets yet; folder absent
│   └── q3-planning/
│       ├── roadmap.md
│       └── roadmap-assets/
│           └── gantt-chart.png
└── personal-wiki/
    ├── .inkclerk/
    │   └── project.json
    ├── index.md
    ├── index-assets/
    │   └── cover.png
    └── recipes/
        ├── sourdough.md
        └── sourdough-assets/
            └── crumb-photo.jpg
```

### Project Identity

The presence of `.inkclerk/project.json` is the authoritative marker that a folder is an InkClerk project.

#### `project.json` schema

```json
{
  "version": 1,
  "id": "018fb29c-0000-7000-8000-000000000001",
  "name": "Meeting Notes",
  "description": "Weekly syncs and planning sessions",
  "created": "2026-06-22T10:00:00Z",
  "lastModified": "2026-06-22T14:30:00Z"
}
```

#### Fields

- `id`: UUID v7 (time-ordered). Generated once at creation; never changes even if the folder is renamed or moved. This is the canonical project identity.
- `name`: human display name; independent of the folder slug.
- `description`: optional human-readable description of the project; may be an empty string if omitted.
- `version`: integer schema version for future migrations.

### Document Identity

Each markdown file carries its own canonical identity as YAML frontmatter at the very top of the file:

```markdown
---
id: 018fb29c-0000-7000-8000-000000000002
created: 2026-06-22T10:00:00Z
lastModified: 2026-06-22T14:30:00Z
---

# My Document

Content here...
```

#### Fields

- `id`: UUID v7 (same family as project IDs). Generated once at file creation; never changes even if the file is renamed or moved. This is the canonical document identity.
- `created`: ISO 8601 UTC timestamp; set once at creation, never updated.
- `lastModified`: ISO 8601 UTC timestamp; updated on every write by the write layer, not the editor.

**Title is not stored in frontmatter.** The document's display name is derived from the first H1 heading, or the filename if no H1 exists.

#### Lifecycle

- **New file**: frontmatter is injected automatically with a fresh UUID and current UTC timestamps.
- **Rename or move**: frontmatter travels with the file unchanged; `id` is stable.
- **Write**: the write layer (`file_write` Tauri command / FastAPI `/files` endpoint) updates `lastModified` on every save.

#### Editor contract

The serializer in `packages/editor/src/serializers/` strips frontmatter before loading content into TipTap and re-injects it (with an updated `lastModified`) when serializing back to disk. Users never see or edit the frontmatter block directly.

#### Lookup

To resolve an `id` to a file path, scan all `.md` files under the project root and read each file's frontmatter `id`. This is a linear scan; a per-project index can be added later if performance requires it.

### Asset folder naming

| Markdown file | Asset folder |
|---|---|
| `note.md` | `note-assets/` |
| `my document.md` | `my document-assets/` |
| `2026-06-kickoff.md` | `2026-06-kickoff-assets/` |
| `deep/nested/report.md` | `deep/nested/report-assets/` |

Rule: strip the `.md` suffix, append `-assets`. Spaces and Unicode are preserved. Asset folders are created **lazily** — only when the first asset is attached to a document.

Images are referenced with `./`-prefixed relative paths:

```markdown
![Alt text](./note-assets/image.png)
```

> **Unicode / CJK filenames**: Folder and file names preserve raw Unicode on disk (e.g. `會議記錄.md` → `會議記錄-assets/`). However, when writing the image reference into the markdown source, **percent-encode the path** rather than embedding raw Unicode characters, because some markdown renderers require it:
> ```markdown
> ![圖片](./%E4%BC%9A%E8%AE%AE%E8%AE%B0%E5%BD%95-assets/%E5%9B%BE%E7%89%87.png)
> ```
> The asset-attach flow in the app should always write percent-encoded paths into `.md` files while keeping actual filenames as raw Unicode on disk. Additionally, note that the 255-byte filesystem limit applies to **bytes not characters** — each CJK character consumes 3 bytes in UTF-8, so the truncation logic for long basenames kicks in after ~85 Chinese characters instead of ~255 ASCII characters.

## Draft/Accept Workflow Design

Implemented once in `packages/editor`; reused by both surfaces.

1. **Formal version**: the `.md` file — what the user last accepted.
2. **Draft version**: stored in `.inkclerk/drafts/<relative-path>.md` (desktop) or in PostgreSQL — `drafts(doc_id, content, created_at, updated_at)` — (web).
3. When a draft exists, the editor opens in **diff mode**: `DraftAddition` / `DraftDeletion` TipTap marks highlight changes computed by `diff-match-patch`.
4. User actions: **Accept all** (draft replaces formal) or **Reject all** (draft discarded). Individual hunk accept/reject is a future enhancement.
5. The editor toggles between WYSIWYG and raw markdown modes; both modes respect the draft layer.
