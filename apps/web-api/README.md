# inkclerk-web-api

FastAPI backend. In v0.1.0 this service is a small, secret-free relay for the Google Doc import handoff (see root `CLAUDE.md`). It never talks to Google and never holds a Google client secret — the browser (`apps/web`'s `/import/google-doc` page) obtains a `drive.file`-scoped access token and picks the target document entirely client-side, via Google Identity Services and the Google Picker. This service just relays the result — `{access_token, expires_in, file_id, file_name, resource_key}` — from that browser page to the local MCP server (`claude-plug-in/mcp/tools/import_google_doc.py`), which has no public endpoint of its own for the browser to reach and instead retrieves the result via a short poll against this service.

Its other planned routers (`/projects`, `/files`, `/drafts`, `/ai`) and PostgreSQL-backed draft storage remain out of scope until Milestone 3.

## Endpoints

- `POST /import/google-doc/session/{session_id}/complete` — body `{"access_token": "...", "expires_in": ..., "file_id": "...", "file_name": "...", "resource_key": ""}`, called by the `apps/web` Picker page's own JS once the user signs in and picks a document. `resource_key` defaults to `""` and is only non-empty for documents in a shared drive. Stores the payload in an in-memory session store keyed by `session_id`, status `"ready"`.
- `GET /import/google-doc/session/{session_id}` — polled by the local MCP tool to retrieve the outcome: `{"status": "pending"}` (not yet completed), `{"status": "ready", "access_token", "expires_in", "file_id", "file_name", "resource_key"}`, or `{"status": "expired"}`. Single-claim: a `"ready"` response can only be read once — any later poll for the same `session_id` returns `"expired"`.

## Environment variables

- `WEB_APP_ORIGIN` — the deployed `apps/web` origin, used to restrict CORS on `POST /import/google-doc/session/{session_id}/complete` (that request is cross-origin, from `apps/web`'s origin to this service). Defaults to `http://localhost:5173` for local development.

## Setup

```bash
uv sync
cp .env.example .env
# then fill in WEB_APP_ORIGIN in .env if it differs from the default
```

## Run

```bash
uv run uvicorn main:app --app-dir src --reload
```

## Test

```bash
uv run pytest
```

## Deployment

Deployed as a Render web service (Docker runtime) pointing at this directory's `Dockerfile`, per the root `render.yaml`. The container's `CMD` binds to `${PORT:-8000}`, honoring Render's injected `$PORT`. `WEB_APP_ORIGIN` is set manually in the Render dashboard (not synced from `render.yaml`).
