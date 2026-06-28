# inkclerk-mcp

MCP server for InkClerk, exposing tools, resources, and prompts to Claude.

## Setup

```bash
uv sync
```

## Usage

**Run** (for integration with Claude Desktop / Claude Code):

```bash
uv run python main.py
```

**Test interactively** with [MCP Inspector](https://github.com/modelcontextprotocol/inspector):

```bash
uv run mcp dev main.py
```

Opens a browser UI at `http://localhost:5173` where you can call tools, browse resources, and try prompts without a real Claude client.
