# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

InkClerk is an AI-first clerical work platform. The core UX contract: **AI edits land as drafts → user reviews diff → user accepts → draft becomes the formal version.** This workflow is implemented once in `packages/editor` and reused across all apps.

The repo is a monorepo using **pnpm workspaces + Turborepo** for the JS/TS layer and **Cargo** for the Tauri Rust backend. Cross-language dev orchestration is via a root `Makefile`.

## Planned Monorepo Structure

```
ink-clerk/
├── apps/
│   ├── desktop/        # Tauri v2 + React (Vite + TypeScript)
│   ├── web/            # React SPA (Vite + TypeScript)
│   └── web-api/        # FastAPI + asyncpg (Python, uv)
├── claude-plug-in/
│   ├── mcp/            # MCP server — tools, resources, prompts (Python)
│   └── skills/         # Claude Code skill definitions (.md)
├── packages/
│   ├── editor/         # @inkclerk/editor — TipTap logic shared by desktop + web
│   ├── ui/             # @inkclerk/ui — shared React components
│   └── ai/             # @inkclerk/ai — provider-agnostic BYOK LLM adapter
├── turbo.json
├── pnpm-workspace.yaml
├── package.json
└── Makefile
```

## Development Commands

> The project is pre-implementation as of v0.1.0. Commands below reflect planned tooling.

| Task | Command |
|---|---|
| Install JS deps | `pnpm install` |
| Build all JS packages | `pnpm turbo build` |
| Dev (all JS apps) | `pnpm turbo dev` |
| Lint | `pnpm turbo lint` |
| Test (JS) | `pnpm turbo test` |
| Run a single JS test | `pnpm --filter <package> test -- <pattern>` |
| Desktop app | `pnpm --filter desktop tauri dev` |
| Web API (Python) | `cd apps/web-api && uv run uvicorn main:app --app-dir src --reload` |
| MCP server | `cd claude-plug-in/mcp && uv run python main.py` |
| MCP Inspector (test) | `cd claude-plug-in/mcp && uv run mcp dev main.py` |

Rust/Tauri builds go through `apps/desktop/src-tauri/` and use `cargo` directly or via `tauri-cli`.

## Development Workflow

Follow TDD: write a failing test first, then write the minimum code to make it pass, then refactor.

## Architecture

### Draft/Accept Workflow (`packages/editor`)

1. **Formal version**: the `.md` file on disk — what the user last accepted.
2. **Draft version**: stored in `.inkclerk/drafts/<relative-path>.md` (desktop) or PostgreSQL `drafts(doc_id, content, created_at, updated_at)` (web).
3. When a draft exists, the editor opens in **diff mode**: `DraftAddition`/`DraftDeletion` TipTap marks highlight changes computed by `diff-match-patch`.
4. User actions: **Accept all** or **Reject all**. Per-hunk accept/reject is a future enhancement.
5. The editor supports a WYSIWYG ↔ raw markdown toggle; both modes respect the draft layer.

### Project Identity

A folder is an InkClerk project when it contains `.inkclerk/project.json`. The `id` field (UUID v7) is the canonical project identity — stable across renames and moves. Default projects root: `~/Documents/InkClerk/`.

### Document Identity

Each `.md` file carries YAML frontmatter with `id` (UUID v7), `created`, and `lastModified`. The serializer in `packages/editor/src/serializers/` strips frontmatter before loading into TipTap and re-injects it (with updated `lastModified`) on save. Users never see frontmatter. **Title is derived from the first H1 heading, not stored in frontmatter.**

### Asset Folders

Asset folders are siblings of their paired `.md` file: `note.md` → `note-assets/`. Created lazily. Images are referenced with `./`-prefixed relative paths. For Unicode/CJK filenames, write **percent-encoded** paths into markdown (e.g. `![](./%E4%BC%9A%E8%AE%AE.png)`) while keeping raw Unicode on disk. Note the 255-byte filesystem limit means CJK basenames truncate after ~85 characters.

### `packages/ai` — BYOK LLM Adapter

Provider-agnostic adapter for the desktop app. `client.ts` exposes a unified `stream`/`complete` interface; per-provider adapters live in `providers/` (Anthropic, OpenAI-compatible, etc.).

### Web API (`apps/web-api`)

FastAPI backend. In v0.1.0 it implements only an `/import/google-doc` router: a small, secret-free relay, deployed on Render, that hands off a `drive.file` access token, picked-file selection, and (for shared-drive documents) a Drive resource key from the browser (`apps/web`'s `/import/google-doc` page, where the user signs in with Google and picks the document entirely client-side via Google Identity Services and the Google Picker) to the local MCP server (see `claude-plug-in/mcp/tools/import_google_doc.py`), which retrieves it by polling a session endpoint — it has no public endpoint of its own for the browser to reach. This service never talks to Google and never holds a Google client secret. The remaining routers — `/projects`, `/files`, `/drafts`, `/ai` — and PostgreSQL-backed (`asyncpg`) draft storage land in Milestone 3 (v0.3.0).

### Claude Plug-in (`claude-plug-in/`)

MCP server (Python) exposing tools, resources, and prompts. Skill definitions are `.md` files in `skills/`. The plug-in is the v0.1.0 milestone target. Google Docs import (`import_google_doc`) is a two-step tool call: the first call opens a browser to `apps/web`'s `/import/google-doc` page for the user to sign in with Google and pick the document, then returns immediately with a `session_id`; once the user confirms they're done, a second call with that `session_id` briefly polls the relay in `apps/web-api` and completes the import.

## Current Milestone

**v0.1.0 — Claude Plug-in**: MCP server tools/resources/prompts + Claude Code skills + client-side Google Picker import flow (`apps/web` `/import/google-doc` page + `apps/web-api` `/import/google-doc` relay router, deployed on Render) + Google Docs import as markdown.
