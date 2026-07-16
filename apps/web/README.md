# inkclerk-web

The InkClerk public web app. In v0.1.0 it is a static homepage, privacy policy, and terms-of-service site — scaffolded ahead of the rest of Milestone 4 (which is where the drafts/editor UI lands) because a public Application home page and privacy policy link are prerequisites for moving the `apps/web-api` Google OAuth consent screen out of Testing mode and into Google's branding verification flow.

## Pages

- `/` (`src/pages/Home.tsx`) — product pitch (the AI-first draft/accept workflow) and the Claude Code plugin install command.
- `/privacy` (`src/pages/Privacy.tsx`) — describes exactly what the OAuth broker collects and how long it's retained. Its claims are sourced directly from `apps/web-api/src/routers/auth.py` (scopes, session TTL, single-claim behavior) — if that service's data handling changes, this page needs to change with it.
- `/terms` (`src/pages/Terms.tsx`) — AS-IS/no-warranty terms and a link to the repo's AGPL-3.0 `LICENSE`.

All three routes share `src/components/Layout.tsx` (header with logo/nav, footer with contact email) via `react-router-dom`'s `<Outlet/>`.

## Scripts

This app is a member of the root pnpm/turbo workspace, not a standalone project — run its scripts from the repo root:

```bash
pnpm --filter web dev        # vite dev server
pnpm turbo build --filter=web  # tsc -b && vite build
pnpm turbo lint --filter=web   # oxlint
pnpm --filter web preview    # preview the production build
```

## Setup

```bash
pnpm install   # from the repo root
```

## Deployment

Deployed as a Render static site (`inkclerk-web` service in the root `render.yaml`), built alongside `inkclerk-web-api` from the same Blueprint. Render auto-activates the pnpm version from the root `package.json`'s `packageManager` field, then the build runs `pnpm install --frozen-lockfile && pnpm turbo build --filter=web`, publishing `apps/web/dist`. A `/* → /index.html` rewrite route is required so `/privacy` and `/terms` resolve correctly on direct load or refresh, since routing is client-side.

After `vite build`, `scripts/prerender.mjs` renders each route (`src/entry-server.tsx` + `react-dom/server`) into real static HTML at `dist/index.html`, `dist/privacy/index.html`, and `dist/terms/index.html`, so the raw HTTP response has visible content without running JS — this matters for crawlers and for Google's OAuth branding reviewer. The client bundle still loads and takes over normally; nothing here is hydration-sensitive since `main.tsx` uses `createRoot`, not `hydrateRoot`.

## Out of scope (for now)

The drafts/editor UI — the rest of Milestone 4 — is not implemented here yet.
