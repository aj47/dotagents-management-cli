# manage-dotagents

A management tool featuring both a lightweight terminal UI (TUI) and a rich Web UI (Control Plane) for managing your `~/.agents` folder. It lets you quickly inspect, sync, and enable/disable skills, agents, tasks, memories, and MCP resources.

It is especially useful for agents like Auggie that do not have this kind of management capability built in.

![manage-dotagents overview](assets/manage-dotagents-overview.png)

## What it does

- **Terminal UI**: A quick management layer directly from your terminal (`manage-dotagents`).
- **Web UI (Control Plane)**: A visual dashboard (React + FastAPI) to view and manage `.agents` configuration in the browser.
- lets you browse skills, agents, tasks, memories, MCP servers, and MCP tools
- sync skills and configurations to various agent targets (e.g. Augment, Cursor, Claude Code)
- supports drilling into individual items
- lets you toggle supported items on/off from the UI/TUI
- lets you bulk-enable or bulk-disable all skills when you want to quickly reshape what agents can access
- supports `global`, `workspace`, and `effective` scope views
- includes doctor, diff, backup, and config-editing command support underneath the UI

## Run it

### Installed CLI (TUI)

- `manage-dotagents`

### Web UI (Control Plane)

The project includes a web-based dashboard for managing `.agents`:

1. Start the API server: `uvicorn dotagents_management_cli.api:app --port 8001 --reload`
2. Start the frontend: `cd ui && npm run dev`

### Local dev (TUI)

- `PYTHONPATH=src python3 -m dotagents_management_cli`

## TUI controls

- `↑/↓` or `j/k` — move
- `Tab` / `→` — move into items
- `←` — go back to categories
- `Enter` — inspect selected item
- `t` — toggle selected item on/off
- `a` — toggle all skills on/off for the current target scope
- `g` / `w` / `e` — set scope
- `s` — cycle scope
- `d` — toggle dry-run
- `r` — refresh
- `o` — status
- `c` — doctor
- `f` — diff
- `q` — quit

## Project layout

- `src/dotagents_management_cli/cli.py` — CLI and TUI implementation
- `tests/test_cli.py` — unit coverage for CLI and TUI helpers
- `docs/dotagents-management-cli-prd.md` — original product requirements