# InkClerk Claude Plug-in

MCP server and Claude Code skills for InkClerk's AI-first draft/accept document workflow:
**AI edits land as drafts → user reviews the diff → user accepts → draft becomes the formal
version.** See the root [`CLAUDE.md`](../CLAUDE.md) for the full project contract.

## What's in this plugin

- **MCP server** (`mcp/`, Python, [FastMCP](https://github.com/modelcontextprotocol/python-sdk)):
  exposes project/document/draft management as MCP tools, a JSON resource dispatcher, and MCP
  prompts for Claude Desktop App users.
- **Claude Code skills** (`skills/`): four `SKILL.md` files defining slash commands under the
  `inkclerk` namespace, each a 1:1 counterpart to one of the MCP prompts below.

## Prerequisites

Python ≥ 3.11 and [`uv`](https://docs.astral.sh/uv/). Google Docs import needs no per-user
Google Cloud setup — authentication is brokered by the hosted `apps/web-api` relay.

## Directory structure

```
claude-plug-in/
├── .claude-plugin/
│   └── plugin.json        # plugin manifest (name, description, version, author)
├── .mcp.json               # wires the MCP server into the plugin
├── mcp/
│   ├── main.py              # imports the shared FastMCP instance, registers tools/resources/prompts
│   ├── pyproject.toml
│   ├── tools/                # create_project, create_document, propose_edit, import_google_doc, ...
│   ├── resources/             # inkclerk://... JSON resource dispatcher
│   ├── prompts/                # MCP Prompts for Claude Desktop App users
│   ├── shared/                  # FastMCP instance, fs/frontmatter/error helpers
│   └── tests/                    # pytest suite
└── skills/
    ├── import-google-doc/SKILL.md
    ├── propose-edit/SKILL.md
    ├── accept-draft/SKILL.md
    └── reject-draft/SKILL.md
```

## Reference

### Tools (`mcp/tools/`)

| Tool | File | Notes |
|---|---|---|
| `create_project(name, description="")` | `projects.py` | |
| `list_projects()` | `projects.py` | read-only |
| `delete_project(project_name)` | `projects.py` | destructive |
| `rename_project(project_name, new_name)` | `projects.py` | destructive |
| `create_document(project_name, filename, subdirectory="", content="")` | `documents.py` | |
| `read_document(project_name, doc_path)` | `documents.py` | read-only |
| `list_documents(project_name)` | `documents.py` | read-only |
| `delete_document(project_name, doc_path)` | `documents.py` | destructive |
| `rename_document(project_name, doc_path, new_filename)` | `documents.py` | destructive |
| `move_document(project_name, doc_path, destination_path, destination_project_name="")` | `documents.py` | |
| `propose_edit(project_name, doc_path, content)` | `drafts.py` | writes a draft, never touches the formal `.md` |
| `get_draft(project_name, doc_path)` | `drafts.py` | read-only |
| `get_diff(project_name, doc_path)` | `drafts.py` | read-only, unified diff vs. the formal version |
| `accept_draft(project_name, doc_path)` | `drafts.py` | destructive — draft becomes the formal version |
| `reject_draft(project_name, doc_path)` | `drafts.py` | destructive — discards the draft |
| `import_google_doc(project_name, filename="", subdirectory="", session_id="")` | `import_google_doc.py` | two-step: first call (no `session_id`) opens a browser for Google sign-in + Picker and returns immediately; second call (with `session_id`) completes the import (see Configuration) |

### Resources (`mcp/resources/resources.py`)

Single dispatcher registered at `inkclerk://{uri}`, handling:

- `inkclerk://projects`
- `inkclerk://project?name=<name>`
- `inkclerk://document?project=<name>&path=<doc_path>`
- `inkclerk://draft?project=<name>&path=<doc_path>`

### Prompts (`mcp/prompts/prompts.py`)

For Claude Desktop App users, who don't get slash commands — each is a 1:1 counterpart to a
skill below: `edit_document`, `create_document`, `import_google_doc`, `accept_draft`.

### Skills (`skills/`)

Claude Code slash commands, invoked as `/inkclerk:<name>`:

| Command | Description |
|---|---|
| `/inkclerk:import-google-doc` | Import a Google Doc into an InkClerk project as a Markdown document |
| `/inkclerk:propose-edit` | Propose an AI-generated edit to a document and write it as a draft |
| `/inkclerk:accept-draft` | Accept the pending draft, making it the formal version of the document |
| `/inkclerk:reject-draft` | Discard the pending draft without modifying the formal document |

## Configuration

`import_google_doc` requires two environment variables:

- `INKCLERK_WEB_APP_URL` — the InkClerk web app, opened in the browser for Google sign-in + Picker
- `INKCLERK_WEB_API_URL` — polled for the sign-in result (a secret-free relay; never talks to
  Google itself, never holds a Google client secret)

`.mcp.json` already ships these pointed at the deployed Render production services
(`https://inkclerk-web.onrender.com`, `https://inkclerk-web-api.onrender.com`), so no local
`apps/web`/`apps/web-api` setup is needed to use this plugin, including for testing (see below).

## Install

**Development (this session only):**
```bash
claude --plugin-dir ./claude-plug-in
```

**Permanent local install:**
```bash
ln -s ~/projects/ink-clerk/claude-plug-in ~/.claude/skills/inkclerk
```

**Marketplace (once published):**
```
/plugin marketplace add anthropics/claude-plugins-community
/plugin install inkclerk@claude-community
```

Either way, confirm the `inkclerk` MCP server connects: run `/mcp` in Claude Code.

## Manual Test Guide

Automated coverage lives in `mcp/tests/` (`cd mcp && uv run pytest`). This section covers the
interactive checks automated tests can't reach: plugin loading, `/mcp` connection status,
slash-command discovery, and the real Google OAuth + Picker round-trip. `.mcp.json` ships
pointing at the deployed Render production services, so none of this requires running `apps/web`
or `apps/web-api` locally.

### Test matrix

| # | Check | Linux/macOS | Windows |
|---|---|---|---|
| 1 | Unit tests (`uv run pytest`) | ✓ | ✓ |
| 2 | `claude plugin validate ./claude-plug-in` | ✓ | ✓ |
| 3 | Claude Code: `/mcp` shows `inkclerk` connected | ✓ | ✓ |
| 4 | Claude Code: `/inkclerk:*` slash commands appear | ✓ | ✓ |
| 5 | Claude Desktop: MCP Prompts appear, tools approve/run | ✓ | ✓ |
| 6 | Full workflow: create project → propose-edit → accept/reject-draft | ✓ | ✓ |
| 7 | Real Google Doc import | ✓ | ✓ |

### Setup

Requires `git`, [`uv`](https://docs.astral.sh/uv/), and the Claude Code CLI.

Windows (PowerShell), if any are missing:
```powershell
winget install --id Git.Git -e
winget install --id Astral-SH.Uv -e
npm install -g @anthropic-ai/claude-code
```

Then, either platform:
```bash
git clone git@github.com:SamuelWang/ink-clerk.git   # or the https:// remote
cd ink-clerk
```

### 1–2. Unit tests + plugin validation
```bash
cd claude-plug-in/mcp && uv sync && uv run pytest
cd ../.. && claude plugin validate ./claude-plug-in
```

### 3–4. Claude Code integration
```bash
claude --plugin-dir ./claude-plug-in
```
`/mcp` → confirm `inkclerk` connected. Slash-command picker → confirm all four `/inkclerk:*`
commands appear.

### 5. Claude Desktop integration

Desktop doesn't read `.claude-plugin/plugin.json`/`.mcp.json` — add the server manually to
Desktop's own config instead:

- Linux: `~/.config/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "inkclerk": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/ink-clerk/claude-plug-in/mcp", "python", "main.py"],
      "env": {
        "INKCLERK_WEB_APP_URL": "https://inkclerk-web.onrender.com",
        "INKCLERK_WEB_API_URL": "https://inkclerk-web-api.onrender.com"
      }
    }
  }
}
```

Use a Windows-style path after `--directory` (e.g. `C:\Users\<you>\ink-clerk\claude-plug-in\mcp`) on that platform.
Restart Claude Desktop, confirm the `inkclerk` server connects, and that the four prompt
templates (`edit_document`, `create_document`, `import_google_doc`, `accept_draft`) are
selectable. There's no slash-command picker or `/mcp` status screen on Desktop — this is the
equivalent check for that surface.

### 6. Non-Google workflow

Invoke `create_project`, then `create_document`, then `propose_edit` with revised content,
`get_diff`, `accept_draft` — and separately `reject_draft` on a second draft. Confirm the formal
`.md` file under `~/Documents/InkClerk/<project>/` (`%USERPROFILE%\Documents\InkClerk\<project>\`
on Windows — resolved automatically via `Path.home()`, no platform-specific code needed) updates
only after accept, and frontmatter (`id`/`created`/`lastModified`) looks right.

### 7. Real Google Doc import

Run `/inkclerk:import-google-doc` (Code) or the `import_google_doc` prompt (Desktop) against a
real Google Doc you own — include one with an inline image to exercise the asset-download path.
Confirm: the browser opens to the Render-hosted `/import/google-doc` page, Google sign-in +
Picker works, and the doc lands as a `.md` file with frontmatter and (if applicable) a
`<slug>-assets/` folder with correctly-referenced images.

### Windows-specific notes

- The symlink-based permanent install (`ln -s ... ~/.claude/skills/inkclerk`, above) doesn't
  translate directly — `New-Item -ItemType SymbolicLink` needs Developer Mode enabled or an
  elevated shell. Not needed for the checks above (`--plugin-dir` / manual Desktop config cover
  them).
- Git may rewrite line endings (CRLF) on checkout; check `git status` after cloning to confirm
  nothing looks unexpectedly modified.
- If SSH auth to GitHub isn't set up on the Windows box, use
  `https://github.com/SamuelWang/ink-clerk.git` instead.
