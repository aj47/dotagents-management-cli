# Managing .agents Configuration

The `manage-dotagents` CLI provides a terminal-based interface for managing your `.agents` configuration. The **interactive TUI is the preferred way** to manage configuration — it provides a visual overview, prevents mistakes, and guides you through common workflows.

## Quick Start

```bash
# Launch the interactive TUI (preferred)
manage-dotagents

# Or with explicit scope
manage-dotagents --global
manage-dotagents --workspace
```

When launched without arguments, the TUI displays an overview of your configuration and lets you browse and modify resources interactively.

## TUI Key Bindings

### Navigation
| Key | Action |
|-----|--------|
| `↑` / `k` | Move up |
| `↓` / `j` | Move down |
| `Tab` / `→` / `l` | Focus items pane |
| `←` / `h` | Return to categories |
| `Enter` | Inspect selected item |

### Actions
| Key | Action |
|-----|--------|
| `t` | Toggle selected item on/off |
| `n` | Add new MCP server (in MCP Servers category) |
| `e` | Edit MCP server (in MCP Servers category) |
| `x` | Remove MCP server (in MCP Servers category) |
| `a` | Toggle all skills on/off (in Skills category) |

### Sync Operations (in Agent Sync category)
| Key | Action |
|-----|--------|
| `p` | Push config to harness (export) |
| `u` | Pull config from harness (import) |
| `b` | Two-way sync (both push and pull) |
| `A` | Toggle auto-sync for selected target |

### Scope & Settings
| Key | Action |
|-----|--------|
| `s` | Cycle through scopes |
| `g` | Set scope to global |
| `w` | Set scope to workspace |
| `d` | Toggle dry-run mode |
| `r` | Refresh data |
| `q` / `Esc` | Quit |

## MCP Server Management

The TUI provides a complete workflow for managing MCP servers:

1. **Navigate** to the "MCP Servers" category
2. **Press `Tab`** or `→` to focus the items list
3. Use these keys:
   - `n` — Add a new server (prompts for ID, transport type, command/URL)
   - `e` — Edit the selected server's configuration
   - `x` — Remove the selected server (with confirmation)
   - `t` — Enable/disable the selected server

Servers from `.agents` configuration are editable. Servers from external harnesses (Claude, Cursor, Windsurf) are displayed but read-only.

## Auto-Sync with Harnesses

Auto-sync automatically pushes your `.agents` configuration to external harnesses (Claude, Cursor, Windsurf) whenever you make changes.

### Enabling Auto-Sync

1. Navigate to "Agent Sync" category in the TUI
2. Select the target harness (e.g., `claude`, `cursor`)
3. Press `A` to toggle auto-sync

When enabled, targets show `[Auto-Sync]` in the TUI. Any mutating command (`enable`, `disable`, `add`, `remove`, `edit`, etc.) will automatically export changes to all auto-sync targets.

### Manual Sync

For one-time syncing without auto-sync:
- `p` — Push (export from .agents to harness)
- `u` — Pull (import from harness to .agents)
- `b` — Both directions

## CLI Commands for Scripting

While the TUI is preferred for interactive use, CLI commands support scripting and automation:

```bash
# Status and inspection
manage-dotagents status
manage-dotagents list skills
manage-dotagents list mcp-servers
manage-dotagents show agent <id>
manage-dotagents doctor

# Enable/disable resources
manage-dotagents enable skill <id>
manage-dotagents disable mcp-server <id>
manage-dotagents enable all-skills

# MCP server management
manage-dotagents add mcp-server <id> --command <cmd> [--args <arg>...] [--env <KEY=VAL>...]
manage-dotagents add mcp-server <id> --url <url>
manage-dotagents edit mcp-server <id> --command <cmd>
manage-dotagents remove mcp-server <id>

# Sync with harnesses
manage-dotagents sync --target claude --push
manage-dotagents sync --target cursor --pull
manage-dotagents sync --target windsurf --both

# Settings
manage-dotagents get setting <key>
manage-dotagents set setting <key> <value>

# Output formats
manage-dotagents list skills --json          # Machine-readable output
manage-dotagents disable skill foo --dry-run # Preview without applying
```

### Scope Flags

All commands accept scope flags:
- `--global` — User-level config (`~/.agents`)
- `--workspace` — Project-level config (`./.agents`)
- `--effective` — Merged view (workspace overrides global)

## Categories

The TUI organizes resources into these categories:

| Category | Description |
|----------|-------------|
| Skills | Agent skill definitions |
| Agents | Agent configurations |
| Tasks | Defined tasks |
| Memories | Agent memory stores |
| MCP Servers | Model Context Protocol servers |
| MCP Tools | Individual MCP tools |
| Agent Sync | Sync targets (Claude, Cursor, Windsurf) |
