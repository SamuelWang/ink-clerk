# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-31

### Added

- MCP server (`claude-plug-in/mcp/`) with 16 tools: project management (4), document management
  (6), draft propose/accept/reject workflow (5), Google Docs import (1).
- `inkclerk://` MCP resource dispatcher (`projects`, `project`, `document`, `draft`).
- 4 MCP prompts for Claude Desktop App users.
- 4 Claude Code skills: `/inkclerk:import-google-doc`, `/inkclerk:propose-edit`,
  `/inkclerk:accept-draft`, `/inkclerk:reject-draft`.
- Google Docs import pipeline: client-side Google sign-in + Picker (`apps/web`), secret-free
  import relay (`apps/web-api`), Drive HTML export, HTML-to-Markdown conversion with inline
  style preservation, image download (including inline `data:` URIs).
- `apps/web` homepage, privacy policy, and terms pages, deployed on Render.
- `apps/web-api` `/import/google-doc` relay, deployed on Render.
- Submission to the Anthropic community marketplace.

[0.1.0]: https://github.com/SamuelWang/ink-clerk/releases/tag/v0.1.0
