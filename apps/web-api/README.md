# inkclerk-web-api

FastAPI backend implementing the hosted Google OAuth broker (see root `CLAUDE.md`).

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
