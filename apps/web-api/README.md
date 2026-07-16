# inkclerk-web-api

FastAPI backend implementing a hosted Google OAuth broker (see root `CLAUDE.md`). It exists so that `import_google_doc` users don't need to set up their own Google Cloud OAuth client — this service brokers `drive.readonly` tokens on behalf of the local MCP server (`claude-plug-in/mcp/tools/import_google_doc.py`).

## Endpoints

- `GET /auth/google/start?session_id=...` — redirects (302) to Google's consent screen, with `state` set to `session_id`.
- `GET /auth/google/callback?code=...&state=...` — exchanges the authorization code for tokens and stores them in an in-memory session store keyed by `state` (5-minute TTL); returns an HTML success or error page.
- `GET /auth/google/session/{session_id}` — polled by the client to retrieve the outcome: `{"status": "pending"}`, `{"status": "ready", "access_token", "refresh_token", "expires_in"}`, or `{"status": "expired"}`. Single-claim: a `"ready"` response can only be read once — any later poll for the same `session_id` returns `"expired"`.
- `POST /auth/refresh` — body `{"refresh_token": "..."}`; returns `{"access_token", "expires_in"}` (plus a rotated `refresh_token` if Google issued a new one), or a 400 error payload if Google rejects the refresh token.

## Environment variables

- `GOOGLE_CLIENT_ID` — OAuth client ID from Google Cloud Console.
- `GOOGLE_CLIENT_SECRET` — OAuth client secret from Google Cloud Console.
- `PUBLIC_BASE_URL` — this service's own public URL, used to build the OAuth redirect URI: `{PUBLIC_BASE_URL}/auth/google/callback`.

## Setup

```bash
uv sync
cp .env.example .env
# then fill in GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / PUBLIC_BASE_URL in .env
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

Deployed as a Render web service (Docker runtime) pointing at this directory's `Dockerfile`, per the root `render.yaml`. The container's `CMD` binds to `${PORT:-8000}`, honoring Render's injected `$PORT`. `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `PUBLIC_BASE_URL` are set manually in the Render dashboard (not synced from `render.yaml`).
