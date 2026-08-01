# InkClerk

InkClerk is an AI-first clerical work platform for managing projects and documents across desktop, web, and Claude Plug-in surfaces.

The core UX contract: **AI edits land as drafts → user reviews the diff → user accepts → draft becomes the formal version.** This workflow is implemented once in `packages/editor` and shared across all apps.

## Apps

| App | Path | Description |
|---|---|---|
| Desktop | `apps/desktop/` | Native app built with Tauri v2 + React. Drafts are stored locally in `.inkclerk/drafts/`. |
| Web | `apps/web/` | React SPA. Uses `@inkclerk/editor` and `@inkclerk/ui`. |
| Web API | `apps/web-api/` | FastAPI backend. In v0.1.0, only the `/import/google-doc` relay is live; `/projects`, `/files`, `/drafts`, and `/ai` endpoints (PostgreSQL-backed draft storage) land in Milestone 3. |
| Claude Plug-in | `claude-plug-in/` | MCP Server (tools, resources, prompts) and Claude Code skill definitions. Installable now — dev install `claude --plugin-dir ./claude-plug-in`, or (pending marketplace approval) `/plugin install inkclerk@claude-community`. See [`claude-plug-in/README.md`](claude-plug-in/README.md). |

## Packages

| Package | Path | Description |
|---|---|---|
| `@inkclerk/editor` | `packages/editor/` | Shared TipTap editor logic: `DraftAddition`/`DraftDeletion` marks, ProseMirror ↔ markdown serializers, and a `diff-match-patch` diff engine. |
| `@inkclerk/ui` | `packages/ui/` | Shared React components: Sidebar, Toolbar, Dialog, DiffOverlay. |
| `@inkclerk/ai` | `packages/ai/` | Provider-agnostic LLM adapter (BYOK). Unified streaming/completion interface over Anthropic, OpenAI-compatible, and other providers. |

## Tech Stack

| Layer | Technology |
|---|---|
| Desktop frontend | React + Vite + TypeScript |
| Desktop backend | Rust (Tauri v2) |
| Web frontend | React + Vite + TypeScript |
| Web backend | Python + FastAPI + asyncpg |
| Database | PostgreSQL |
| Editor | TipTap (ProseMirror) |
| AI | Anthropic API (`anthropic` Python SDK / `@inkclerk/ai`) |
| Monorepo tooling | pnpm workspaces + Turborepo |

## Docs

- [Architecture](docs/architecture.md) — repository structure, file layout, project/document identity, draft/accept workflow design
- [Roadmap](docs/roadmap.md) — milestone plan from v0.1 (Claude Plug-in) through v0.5 (Sync)
- [v0.1.0 Release Notes](docs/releases/v0.1.0.md) — what shipped in the Claude Plug-in milestone, install instructions, known gaps
