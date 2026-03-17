from __future__ import annotations

import argparse
import curses
import json
import os
import shutil
import sys
import tempfile
import textwrap
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TextIO

RESOURCE_TYPES = ("skills", "agents", "tasks", "memories")
SINGULAR_NAMES = {
    "skills": "skill",
    "agents": "agent",
    "tasks": "task",
    "memories": "memory",
}
METADATA_FILES = {
    "agents": ("agent.md", "AGENT.md", "README.md"),
    "tasks": ("task.md", "TASK.md", "README.md"),
}
SETTINGS_FILES = ("dotagents-settings.json", "speakmcp-settings.json")
SECRET_HINTS = ("secret", "token", "password", "apikey", "api_key", "key")
MUTATING_COMMANDS = {"enable", "disable", "allow", "deny", "set", "backup"}
RESOURCE_ACTION_OPTIONS = [
    ("skill", "Skill"),
    ("agent", "Agent"),
    ("task", "Task"),
    ("memory", "Memory"),
    ("mcp-server", "MCP server"),
    ("mcp-tool", "MCP tool"),
]
LIST_ACTION_OPTIONS = [
    ("skills", "Skills"),
    ("agents", "Agents"),
    ("tasks", "Tasks"),
    ("memories", "Memories"),
    ("mcp-servers", "MCP servers"),
    ("mcp-tools", "MCP tools"),
    ("backups", "Backups"),
]
WRITE_SCOPE_OPTIONS = [("global", "Global (~/.agents)"), ("workspace", "Workspace (<project>/.agents)")]
ALL_SCOPE_OPTIONS = [("effective", "Effective"), ("workspace", "Workspace"), ("global", "Global")]
BACKUP_ACTION_OPTIONS = [("create", "Create backup"), ("restore", "Restore backup")]


class CliError(RuntimeError):
    pass


@dataclass
class CommandResult:
    payload: Any
    human_text: str
    exit_code: int = 0


@dataclass
class AppContext:
    cwd: Path
    global_root: Path
    workspace_root: Path


@dataclass(frozen=True)
class TuiCategory:
    key: str
    label: str
    toggle_type: str


@dataclass
class TuiBrowserData:
    categories: list[TuiCategory]
    items_by_category: dict[str, list[dict[str, Any]]]
    warnings: list[str]


@dataclass
class TuiState:
    scope: str
    dry_run: bool
    focus: str = "categories"
    selected_category_index: int = 0
    selected_item_index: int = 0
    last_output: str = "Welcome to manage-dotagents. Browse categories, inspect items, and press `t` to toggle the selected item."
    status_message: str = "Ready"


def build_parser(*, require_command: bool = True) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="manage-dotagents",
        description="Manage .agents configuration from one CLI.",
        epilog="Run `manage-dotagents` with no subcommand to enter interactive mode.",
    )
    scope_group = parser.add_mutually_exclusive_group()
    scope_group.add_argument("--global", dest="scope", action="store_const", const="global")
    scope_group.add_argument("--workspace", dest="scope", action="store_const", const="workspace")
    scope_group.add_argument("--effective", dest="scope", action="store_const", const="effective")
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument("--dry-run", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=require_command)

    subparsers.add_parser("status")
    subparsers.add_parser("doctor")
    subparsers.add_parser("diff")

    list_parser = subparsers.add_parser("list")
    list_subparsers = list_parser.add_subparsers(dest="list_type", required=True)
    for item in ("skills", "agents", "tasks", "memories", "mcp-servers", "mcp-tools", "backups"):
        list_subparsers.add_parser(item)

    show_parser = subparsers.add_parser("show")
    show_subparsers = show_parser.add_subparsers(dest="show_type", required=True)
    agent_parser = show_subparsers.add_parser("agent")
    agent_parser.add_argument("id")

    get_parser = subparsers.add_parser("get")
    get_subparsers = get_parser.add_subparsers(dest="get_type", required=True)
    setting_get = get_subparsers.add_parser("setting")
    setting_get.add_argument("key")

    set_parser = subparsers.add_parser("set")
    set_subparsers = set_parser.add_subparsers(dest="set_type", required=True)
    for kind in ("setting", "model"):
        item_parser = set_subparsers.add_parser(kind)
        item_parser.add_argument("key")
        item_parser.add_argument("value")

    enable_parser = subparsers.add_parser("enable")
    enable_subparsers = enable_parser.add_subparsers(dest="enable_type", required=True)
    for kind in ("skill", "agent", "task", "memory", "mcp-server", "mcp-tool"):
        item_parser = enable_subparsers.add_parser(kind)
        item_parser.add_argument("id")

    disable_parser = subparsers.add_parser("disable")
    disable_subparsers = disable_parser.add_subparsers(dest="disable_type", required=True)
    for kind in ("skill", "agent", "task", "memory", "mcp-server", "mcp-tool"):
        item_parser = disable_subparsers.add_parser(kind)
        item_parser.add_argument("id")

    for verb in ("allow", "deny"):
        parser_obj = subparsers.add_parser(verb)
        verb_subparsers = parser_obj.add_subparsers(dest=f"{verb}_type", required=True)
        skill_parser = verb_subparsers.add_parser("skill")
        skill_parser.add_argument("skill_id")
        skill_parser.add_argument("--agent", dest="agent_id", required=True)

    backup_parser = subparsers.add_parser("backup")
    backup_subparsers = backup_parser.add_subparsers(dest="backup_type", required=True)
    backup_subparsers.add_parser("create")
    restore_parser = backup_subparsers.add_parser("restore")
    restore_parser.add_argument("backup_id")

    return parser


def build_context(cwd: Path | None = None, env: dict[str, str] | None = None) -> AppContext:
    cwd = (cwd or Path.cwd()).resolve()
    env = env or os.environ
    global_root = Path(env.get("DOTAGENTS_GLOBAL_HOME", str(Path.home() / ".agents"))).expanduser().resolve()
    workspace_base = Path(env.get("DOTAGENTS_WORKSPACE_ROOT", str(cwd))).resolve()
    return AppContext(cwd=cwd, global_root=global_root, workspace_root=workspace_base / ".agents")


def scope_path(ctx: AppContext, scope: str) -> Path:
    return ctx.global_root if scope == "global" else ctx.workspace_root


def resolve_read_scope(args: argparse.Namespace, ctx: AppContext) -> str:
    if args.scope:
        return args.scope
    return "effective"


def resolve_write_scope(args: argparse.Namespace, ctx: AppContext) -> str:
    if args.scope == "effective":
        raise CliError("Mutating commands require --global or --workspace; --effective is read-only.")
    if args.scope:
        return args.scope
    return "workspace" if ctx.workspace_root.exists() else "global"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def parse_value(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        lowered = raw.lower()
        if lowered in {"true", "false"}:
            return lowered == "true"
        if lowered == "null":
            return None
        try:
            return int(raw)
        except ValueError:
            try:
                return float(raw)
            except ValueError:
                return raw


def atomic_write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=path.parent, encoding="utf-8") as handle:
        handle.write(text)
        temp_path = Path(handle.name)
    temp_path.replace(path)


def atomic_write_json(path: Path, data: Any) -> None:
    atomic_write_text(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def load_json_object(path: Path, *, create_default: bool = False) -> dict[str, Any]:
    if not path.exists():
        if create_default:
            return {}
        raise CliError(f"Missing JSON file: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliError(f"Malformed `{path.name}`: expected valid JSON object.") from exc
    if not isinstance(data, dict):
        raise CliError(f"Malformed `{path.name}`: expected valid JSON object.")
    return data


def split_key_path(key: str) -> list[str]:
    return [part for part in key.split(".") if part]


def get_nested_value(data: dict[str, Any], key: str) -> Any:
    current: Any = data
    for part in split_key_path(key):
        if not isinstance(current, dict) or part not in current:
            raise CliError(f"Unknown key path `{key}`.")
        current = current[part]
    return current


def set_nested_value(data: dict[str, Any], key: str, value: Any) -> None:
    parts = split_key_path(key)
    if not parts:
        raise CliError("Key path cannot be empty.")
    current = data
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        elif not isinstance(current[part], dict):
            raise CliError(f"Cannot set `{key}` because `{part}` is not an object.")
        current = current[part]
    current[parts[-1]] = value


def resolve_settings_file(root: Path) -> Path:
    for name in SETTINGS_FILES:
        candidate = root / name
        if candidate.exists():
            return candidate
    return root / SETTINGS_FILES[0]


def resolve_json_file(root: Path, file_name: str) -> Path:
    return resolve_settings_file(root) if file_name == "settings" else root / file_name


def parse_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        raise CliError(f"Malformed frontmatter in `{path}`.")
    header = text[4:end]
    body = text[end + 5 :]
    meta: dict[str, Any] = {}
    for raw_line in header.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise CliError(f"Malformed frontmatter in `{path}`.")
        key, raw_value = line.split(":", 1)
        meta[key.strip()] = parse_value(raw_value.strip())
    return meta, body


def write_frontmatter(path: Path, meta: dict[str, Any], body: str) -> None:
    header = ["---"]
    for key, value in meta.items():
        if isinstance(value, bool):
            serialized = "true" if value else "false"
        elif value is None:
            serialized = "null"
        elif isinstance(value, (int, float)):
            serialized = str(value)
        else:
            serialized = json.dumps(value)
        header.append(f"{key}: {serialized}")
    header.append("---")
    text = "\n".join(header) + "\n"
    if body:
        text += body.lstrip("\n")
    atomic_write_text(path, text)


def metadata_path(resource_path: Path, resource_type: str) -> Path | None:
    for name in METADATA_FILES.get(resource_type, ()):  # type: ignore[arg-type]
        candidate = resource_path / name
        if candidate.exists():
            return candidate
    if resource_type == "agents":
        return resource_path / "agent.md"
    if resource_type == "tasks":
        return resource_path / "task.md"
    return None


def scan_resources_in_scope(scope_name: str, root: Path) -> dict[str, dict[str, dict[str, Any]]]:
    resources: dict[str, dict[str, dict[str, Any]]] = {kind: {} for kind in RESOURCE_TYPES}
    for kind in RESOURCE_TYPES:
        active_dir = root / kind
        disabled_dir = root / ".disabled" / kind
        for base_dir, state in ((active_dir, "present"), (disabled_dir, "disabled")):
            if not base_dir.exists():
                continue
            for item in sorted(base_dir.iterdir()):
                if not item.is_dir():
                    continue
                existing = resources[kind].get(item.name)
                if existing and state == "disabled":
                    existing["has_disabled_copy"] = True
                    existing["disabled_path"] = str(item)
                    continue
                resource = {
                    "id": item.name,
                    "type": SINGULAR_NAMES[kind],
                    "scope": scope_name,
                    "source_path": str(item),
                    "current_state": state,
                    "reason": "",
                }
                if kind in {"agents", "tasks"} and state == "present":
                    meta_file = metadata_path(item, kind)
                    if meta_file:
                        meta, _ = parse_frontmatter(meta_file)
                        enabled = meta.get("enabled", True)
                        if not isinstance(enabled, bool):
                            raise CliError(f"Malformed frontmatter in `{meta_file}`.")
                        resource["metadata_enabled"] = enabled
                        if not enabled:
                            resource["current_state"] = "disabled-metadata"
                            resource["reason"] = f"{meta_file.name} sets enabled: false"
                if state == "disabled":
                    resource["reason"] = f"Moved to {disabled_dir}"
                resources[kind][item.name] = resource
    return resources


def merge_effective(global_scan: dict[str, dict[str, dict[str, Any]]], workspace_scan: dict[str, dict[str, dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    merged: dict[str, list[dict[str, Any]]] = {kind: [] for kind in RESOURCE_TYPES}
    for kind in RESOURCE_TYPES:
        ids = sorted(set(global_scan[kind]) | set(workspace_scan[kind]))
        for resource_id in ids:
            chosen = workspace_scan[kind].get(resource_id) or global_scan[kind].get(resource_id)
            if not chosen:
                continue
            entry = dict(chosen)
            entry["effective_status"] = "active" if chosen["current_state"] == "present" else "inactive"
            if chosen["current_state"] == "disabled-metadata":
                entry["effective_status"] = "inactive"
            merged[kind].append(entry)
    return merged


def collect_resources(ctx: AppContext, scope: str) -> dict[str, list[dict[str, Any]]]:
    if scope == "global":
        return {k: list(v.values()) for k, v in scan_resources_in_scope("global", ctx.global_root).items()}
    if scope == "workspace":
        return {k: list(v.values()) for k, v in scan_resources_in_scope("workspace", ctx.workspace_root).items()}
    return merge_effective(
        scan_resources_in_scope("global", ctx.global_root),
        scan_resources_in_scope("workspace", ctx.workspace_root),
    )


def flatten_resources(resources: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for kind in RESOURCE_TYPES:
        rows.extend(sorted(resources[kind], key=lambda item: item["id"]))
    return rows


def read_json_for_scope(ctx: AppContext, scope: str, file_name: str) -> tuple[Path, dict[str, Any]]:
    if scope == "effective":
        workspace_path = resolve_json_file(ctx.workspace_root, file_name)
        if workspace_path.exists():
            return workspace_path, load_json_object(workspace_path)
        global_path = resolve_json_file(ctx.global_root, file_name)
        if global_path.exists():
            return global_path, load_json_object(global_path)
        return workspace_path, {}
    root = scope_path(ctx, scope)
    path = resolve_json_file(root, file_name)
    if path.exists():
        return path, load_json_object(path)
    return path, {}


def read_managed_json(ctx: AppContext, scope: str, file_name: str) -> tuple[Path, dict[str, Any]]:
    if scope == "effective":
        return read_json_for_scope(ctx, scope, file_name)
    path = resolve_json_file(scope_path(ctx, scope), file_name)
    if path.exists():
        return path, load_json_object(path)
    return path, {}


def mcp_servers_from_config(config: dict[str, Any]) -> dict[str, Any]:
    raw = config.get("mcpServers") or config.get("servers") or {}
    return raw if isinstance(raw, dict) else {}


def mcp_disabled_servers(config: dict[str, Any]) -> set[str]:
    raw = config.get("mcpRuntimeDisabledServers") or []
    return {str(item) for item in raw if isinstance(item, (str, int, float))}


def mcp_disabled_tools(config: dict[str, Any]) -> set[str]:
    raw = config.get("mcpDisabledTools") or []
    return {str(item) for item in raw if isinstance(item, (str, int, float))}


def mcp_tools_from_config(config: dict[str, Any]) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    top_level = config.get("mcpTools") or config.get("tools") or {}
    if isinstance(top_level, dict):
        for tool_id, value in top_level.items():
            tools.append({"id": str(tool_id), "source": "top-level", "config": value})
    elif isinstance(top_level, list):
        for item in top_level:
            if isinstance(item, str):
                tools.append({"id": item, "source": "top-level", "config": {}})
            elif isinstance(item, dict):
                tool_id = item.get("id") or item.get("name")
                if tool_id:
                    tools.append({"id": str(tool_id), "source": "top-level", "config": item})
    for server_id, server_cfg in mcp_servers_from_config(config).items():
        if not isinstance(server_cfg, dict):
            continue
        server_tools = server_cfg.get("tools") or {}
        if isinstance(server_tools, dict):
            for tool_id, value in server_tools.items():
                tools.append({"id": f"{server_id}.{tool_id}", "source": server_id, "config": value})
        elif isinstance(server_tools, list):
            for item in server_tools:
                if isinstance(item, str):
                    tools.append({"id": f"{server_id}.{item}", "source": server_id, "config": {}})
                elif isinstance(item, dict):
                    tool_id = item.get("id") or item.get("name")
                    if tool_id:
                        tools.append({"id": f"{server_id}.{tool_id}", "source": server_id, "config": item})
    return sorted(tools, key=lambda item: item["id"])


def build_mcp_server_rows(path: Path, config: dict[str, Any], scope: str) -> list[dict[str, Any]]:
    disabled = mcp_disabled_servers(config)
    rows = []
    for server_id in sorted(mcp_servers_from_config(config)):
        rows.append(
            {
                "id": server_id,
                "type": "mcp-server",
                "current_state": "disabled" if server_id in disabled else "present",
                "scope": scope,
                "source_path": str(path),
                "reason": "runtime-disabled in mcp.json" if server_id in disabled else "",
            }
        )
    return rows


def build_mcp_tool_rows(path: Path, config: dict[str, Any], scope: str) -> list[dict[str, Any]]:
    disabled = mcp_disabled_tools(config)
    rows = []
    for tool in mcp_tools_from_config(config):
        rows.append(
            {
                "id": tool["id"],
                "type": "mcp-tool",
                "current_state": "disabled" if tool["id"] in disabled else "present",
                "scope": scope,
                "source_path": str(path),
                "reason": "disabled in mcp.json" if tool["id"] in disabled else "",
            }
        )
    return rows


def redact_value(key: str, value: Any) -> Any:
    lowered = key.lower()
    if any(hint in lowered for hint in SECRET_HINTS):
        return "<redacted>"
    if isinstance(value, dict):
        return {sub_key: redact_value(sub_key, sub_value) for sub_key, sub_value in value.items()}
    if isinstance(value, list):
        return [redact_value(key, item) for item in value]
    return value


def make_backup(root: Path, reason: str, dry_run: bool = False) -> dict[str, Any]:
    backup_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    backup_root = root / ".backups" / backup_id
    if backup_root.exists():
        backup_id = f"{backup_id}-{uuid.uuid4().hex[:6]}"
        backup_root = root / ".backups" / backup_id
    payload = {"id": backup_id, "path": str(backup_root), "reason": reason, "created": backup_id}
    if dry_run:
        payload["dry_run"] = True
        return payload
    ensure_dir(root)
    ensure_dir(backup_root / "snapshot")
    for item in root.iterdir():
        if item.name == ".backups":
            continue
        destination = backup_root / "snapshot" / item.name
        if item.is_dir():
            shutil.copytree(item, destination)
        else:
            shutil.copy2(item, destination)
    atomic_write_json(backup_root / "metadata.json", payload)
    return payload


def restore_backup(root: Path, backup_id: str, dry_run: bool = False) -> dict[str, Any]:
    backup_root = root / ".backups" / backup_id
    snapshot_dir = backup_root / "snapshot"
    if not snapshot_dir.exists():
        raise CliError(f"Unknown backup `{backup_id}`.")
    changes = {"restored": backup_id, "scope_path": str(root), "dry_run": dry_run}
    if dry_run:
        return changes
    ensure_dir(root)
    for item in list(root.iterdir()):
        if item.name == ".backups":
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()
    for item in snapshot_dir.iterdir():
        destination = root / item.name
        if item.is_dir():
            shutil.copytree(item, destination)
        else:
            shutil.copy2(item, destination)
    return changes


def move_resource(root: Path, resource_type: str, resource_id: str, direction: str, dry_run: bool = False) -> dict[str, Any]:
    active_path = root / f"{resource_type}s" / resource_id
    disabled_path = root / ".disabled" / f"{resource_type}s" / resource_id
    if direction == "disable":
        if disabled_path.exists():
            raise CliError(f"{resource_type.title()} exists but is already disabled at `{disabled_path}`.")
        if not active_path.exists():
            raise CliError(f"Unknown {resource_type} `{resource_id}`.")
        if dry_run:
            return {"action": "disable", "type": resource_type, "id": resource_id, "from": str(active_path), "to": str(disabled_path), "dry_run": True}
        ensure_dir(disabled_path.parent)
        active_path.rename(disabled_path)
        return {"action": "disable", "type": resource_type, "id": resource_id, "from": str(active_path), "to": str(disabled_path)}
    if active_path.exists():
        raise CliError(f"Cannot enable {resource_type} because `{active_path}` already exists.")
    if not disabled_path.exists():
        raise CliError(f"Unknown disabled {resource_type} `{resource_id}`.")
    if dry_run:
        return {"action": "enable", "type": resource_type, "id": resource_id, "from": str(disabled_path), "to": str(active_path), "dry_run": True}
    ensure_dir(active_path.parent)
    disabled_path.rename(active_path)
    return {"action": "enable", "type": resource_type, "id": resource_id, "from": str(disabled_path), "to": str(active_path)}


def toggle_metadata_resource(root: Path, resource_type: str, resource_id: str, enabled: bool, dry_run: bool = False) -> dict[str, Any]:
    resource_dir = root / f"{resource_type}s" / resource_id
    disabled_dir = root / ".disabled" / f"{resource_type}s" / resource_id
    if not resource_dir.exists():
        if disabled_dir.exists() and enabled:
            return move_resource(root, resource_type, resource_id, "enable", dry_run=dry_run)
        raise CliError(f"Unknown {resource_type} `{resource_id}`.")
    meta_path = metadata_path(resource_dir, f"{resource_type}s")
    if not meta_path:
        raise CliError(f"{resource_type.title()} `{resource_id}` does not support metadata toggles.")
    meta, body = parse_frontmatter(meta_path)
    meta["enabled"] = enabled
    payload = {"action": "enable" if enabled else "disable", "type": resource_type, "id": resource_id, "path": str(meta_path), "enabled": enabled, "dry_run": dry_run}
    if dry_run:
        return payload
    write_frontmatter(meta_path, meta, body)
    return payload


def update_json_array(config: dict[str, Any], key: str, item_id: str, enabled: bool) -> None:
    current = list(config.get(key) or [])
    values = [str(item) for item in current]
    if enabled:
        values = [value for value in values if value != item_id]
    elif item_id not in values:
        values.append(item_id)
    config[key] = values


def mutate_mcp(ctx: AppContext, scope: str, item_type: str, item_id: str, enabled: bool, dry_run: bool = False) -> dict[str, Any]:
    path, config = read_managed_json(ctx, scope, "mcp.json")
    if item_type == "mcp-server":
        if item_id not in mcp_servers_from_config(config):
            raise CliError(f"Unknown mcp-server `{item_id}`.")
        update_json_array(config, "mcpRuntimeDisabledServers", item_id, enabled)
    else:
        tool_ids = {item["id"] for item in mcp_tools_from_config(config)}
        if item_id not in tool_ids:
            raise CliError(f"Unknown mcp-tool `{item_id}`.")
        update_json_array(config, "mcpDisabledTools", item_id, enabled)
    payload = {"action": "enable" if enabled else "disable", "type": item_type, "id": item_id, "path": str(path), "dry_run": dry_run}
    if dry_run:
        return payload
    atomic_write_json(path, config)
    return payload


def mutate_setting(ctx: AppContext, scope: str, file_kind: str, key: str, value: Any, dry_run: bool = False) -> dict[str, Any]:
    file_name = "settings" if file_kind == "setting" else "models.json"
    path, config = read_managed_json(ctx, scope, file_name)
    set_nested_value(config, key, value)
    payload = {"action": "set", "type": file_kind, "key": key, "value": redact_value(key, value), "path": str(path), "dry_run": dry_run}
    if dry_run:
        return payload
    atomic_write_json(path, config)
    return payload


def mutate_skill_permission(ctx: AppContext, scope: str, agent_id: str, skill_id: str, allowed: bool, dry_run: bool = False) -> dict[str, Any]:
    agent_dir = scope_path(ctx, scope) / "agents" / agent_id
    if not agent_dir.exists():
        raise CliError(f"Unknown agent `{agent_id}`.")
    config_path = agent_dir / "config.json"
    config = load_json_object(config_path, create_default=True) if config_path.exists() else {}
    skills_cfg = config.setdefault("skillsConfig", {})
    if not isinstance(skills_cfg, dict):
        raise CliError(f"Malformed `{config_path.name}`: skillsConfig must be an object.")
    all_disabled = bool(skills_cfg.get("allSkillsDisabledByDefault", False))
    enabled_ids = [str(item) for item in skills_cfg.get("enabledSkillIds") or []]
    disabled_ids = [str(item) for item in skills_cfg.get("disabledSkillIds") or []]
    if allowed:
        disabled_ids = [item for item in disabled_ids if item != skill_id]
        if all_disabled and skill_id not in enabled_ids:
            enabled_ids.append(skill_id)
    else:
        enabled_ids = [item for item in enabled_ids if item != skill_id]
        if not all_disabled and skill_id not in disabled_ids:
            disabled_ids.append(skill_id)
    skills_cfg["enabledSkillIds"] = enabled_ids
    skills_cfg["disabledSkillIds"] = disabled_ids
    payload = {"action": "allow" if allowed else "deny", "type": "skill-permission", "agent": agent_id, "skill": skill_id, "path": str(config_path), "dry_run": dry_run}
    if dry_run:
        return payload
    atomic_write_json(config_path, config)
    return payload


def resource_rows_for_kind(ctx: AppContext, scope: str, kind: str) -> list[dict[str, Any]]:
    resources = collect_resources(ctx, scope)
    return resources[kind]


def status_command(ctx: AppContext, scope: str) -> CommandResult:
    resources = collect_resources(ctx, scope)
    rows = flatten_resources(resources)
    summary = {kind: len(resources[kind]) for kind in RESOURCE_TYPES}
    text = [f"Scope: {scope}"]
    text.append("Summary: " + ", ".join(f"{kind}={count}" for kind, count in summary.items()))
    text.append(render_table(rows, ["id", "type", "current_state", "scope", "source_path", "reason"]))
    return CommandResult(payload={"scope": scope, "summary": summary, "resources": rows}, human_text="\n".join(text))


def list_command(ctx: AppContext, scope: str, list_type: str) -> CommandResult:
    if list_type in RESOURCE_TYPES:
        rows = resource_rows_for_kind(ctx, scope, list_type)
        return CommandResult(payload={"scope": scope, "type": list_type, "items": rows}, human_text=render_table(rows, ["id", "type", "current_state", "scope", "source_path", "reason"]))
    if list_type == "mcp-servers":
        path, config = read_json_for_scope(ctx, scope, "mcp.json")
        rows = build_mcp_server_rows(path, config, scope)
        return CommandResult(payload={"scope": scope, "type": list_type, "items": rows}, human_text=render_table(rows, ["id", "type", "current_state", "scope", "reason"]))
    if list_type == "mcp-tools":
        path, config = read_json_for_scope(ctx, scope, "mcp.json")
        rows = build_mcp_tool_rows(path, config, scope)
        return CommandResult(payload={"scope": scope, "type": list_type, "items": rows}, human_text=render_table(rows, ["id", "type", "current_state", "scope", "reason"]))
    backup_root = scope_path(ctx, scope) / ".backups"
    rows = []
    if backup_root.exists():
        for item in sorted(backup_root.iterdir()):
            metadata = item / "metadata.json"
            payload = load_json_object(metadata) if metadata.exists() else {"reason": "missing metadata"}
            rows.append({"id": item.name, "type": "backup", "reason": payload.get("reason", ""), "path": str(item)})
    return CommandResult(payload={"scope": scope, "type": "backups", "items": rows}, human_text=render_table(rows, ["id", "type", "reason", "path"]))


def get_setting_command(ctx: AppContext, scope: str, key: str) -> CommandResult:
    path, config = read_json_for_scope(ctx, scope, "settings")
    value = get_nested_value(config, key)
    payload = {"scope": scope, "path": str(path), "key": key, "value": redact_value(key, value)}
    return CommandResult(payload=payload, human_text=f"{key} = {json.dumps(payload['value'])}")


def build_skill_availability(skill: dict[str, Any], agent_cfg: dict[str, Any]) -> dict[str, Any]:
    skills_cfg = agent_cfg.get("skillsConfig") or {}
    enabled_ids = {str(item) for item in skills_cfg.get("enabledSkillIds") or []}
    disabled_ids = {str(item) for item in skills_cfg.get("disabledSkillIds") or []}
    all_disabled = bool(skills_cfg.get("allSkillsDisabledByDefault", False))
    if skill["current_state"] != "present":
        return {"id": skill["id"], "available": False, "reason": skill.get("reason") or skill["current_state"]}
    if skill["id"] in disabled_ids:
        return {"id": skill["id"], "available": False, "reason": "disabledSkillIds contains the skill"}
    if all_disabled and skill["id"] not in enabled_ids:
        return {"id": skill["id"], "available": False, "reason": "allSkillsDisabledByDefault is true and skill is not in enabledSkillIds"}
    return {"id": skill["id"], "available": True, "reason": "available"}


def show_agent_command(ctx: AppContext, scope: str, agent_id: str) -> CommandResult:
    agents = {item["id"]: item for item in resource_rows_for_kind(ctx, scope, "agents")}
    if agent_id not in agents:
        raise CliError(f"Unknown agent `{agent_id}`.")
    agent = agents[agent_id]
    config_path = Path(agent["source_path"]) / "config.json"
    config = load_json_object(config_path, create_default=True) if config_path.exists() else {}
    skills = [build_skill_availability(skill, config) for skill in resource_rows_for_kind(ctx, scope, "skills")]
    tool_cfg = config.get("toolConfig") or {}
    payload = {"agent": agent, "skills": skills, "toolConfig": redact_value("toolConfig", tool_cfg)}
    lines = [f"Agent: {agent_id}", f"State: {agent['current_state']}", f"Path: {agent['source_path']}", "Skills:"]
    lines.append(render_table(skills, ["id", "available", "reason"]))
    return CommandResult(payload=payload, human_text="\n".join(lines))


def diff_command(ctx: AppContext) -> CommandResult:
    global_resources = collect_resources(ctx, "global")
    workspace_resources = collect_resources(ctx, "workspace")
    effective_resources = collect_resources(ctx, "effective")
    rows = []
    for kind in RESOURCE_TYPES:
        ids = sorted({item["id"] for item in global_resources[kind]} | {item["id"] for item in workspace_resources[kind]})
        global_map = {item["id"]: item for item in global_resources[kind]}
        workspace_map = {item["id"]: item for item in workspace_resources[kind]}
        effective_map = {item["id"]: item for item in effective_resources[kind]}
        for resource_id in ids:
            rows.append({
                "id": resource_id,
                "type": SINGULAR_NAMES[kind],
                "global_state": global_map.get(resource_id, {}).get("current_state", "missing"),
                "workspace_state": workspace_map.get(resource_id, {}).get("current_state", "missing"),
                "effective_state": effective_map.get(resource_id, {}).get("current_state", "missing"),
            })
    return CommandResult(payload={"diff": rows}, human_text=render_table(rows, ["id", "type", "global_state", "workspace_state", "effective_state"]))


def doctor_command(ctx: AppContext, scope: str) -> CommandResult:
    diagnostics: list[dict[str, Any]] = []
    scopes = [scope] if scope in {"global", "workspace"} else ["global", "workspace"]
    effective_skills = {item["id"] for item in resource_rows_for_kind(ctx, "effective", "skills") if item["current_state"] == "present"}
    for scope_name in scopes:
        root = scope_path(ctx, scope_name)
        if not root.exists():
            continue
        for file_name in ("mcp.json", "models.json") + SETTINGS_FILES:
            file_path = root / file_name
            if file_path.exists():
                try:
                    load_json_object(file_path)
                except CliError as exc:
                    diagnostics.append({"severity": "error", "scope": scope_name, "path": str(file_path), "message": str(exc)})
        resources = scan_resources_in_scope(scope_name, root)
        active_agents = root / "agents"
        disabled_agents = root / ".disabled" / "agents"
        active_tasks = root / "tasks"
        disabled_tasks = root / ".disabled" / "tasks"
        for kind in ("agents", "tasks"):
            for item in resources[kind].values():
                item_path = Path(item["source_path"])
                meta_file = metadata_path(item_path, kind)
                if meta_file and meta_file.exists():
                    try:
                        meta, _ = parse_frontmatter(meta_file)
                        enabled = meta.get("enabled", True)
                        if not isinstance(enabled, bool):
                            raise CliError(f"Malformed frontmatter in `{meta_file}`.")
                    except CliError as exc:
                        diagnostics.append({"severity": "error", "scope": scope_name, "path": str(meta_file), "message": str(exc)})
                disabled_match = root / ".disabled" / kind / item["id"]
                if item["current_state"] == "disabled-metadata" and disabled_match.exists():
                    diagnostics.append({"severity": "warning", "scope": scope_name, "path": str(disabled_match), "message": f"Conflicting state for {SINGULAR_NAMES[kind]} `{item['id']}`: disabled in metadata and move-based store."})
                config_path = item_path / "config.json"
                if kind == "agents" and config_path.exists():
                    try:
                        config = load_json_object(config_path)
                        skills_cfg = config.get("skillsConfig") or {}
                        for key in ("enabledSkillIds", "disabledSkillIds"):
                            for skill_id in skills_cfg.get(key) or []:
                                if str(skill_id) not in effective_skills:
                                    diagnostics.append({"severity": "error", "scope": scope_name, "path": str(config_path), "message": f"Agent `{item['id']}` references missing skill `{skill_id}`."})
                    except CliError as exc:
                        diagnostics.append({"severity": "error", "scope": scope_name, "path": str(config_path), "message": str(exc)})
        if active_agents.exists() and disabled_agents.exists():
            for item in active_agents.iterdir():
                if item.is_dir() and (disabled_agents / item.name).exists():
                    diagnostics.append({"severity": "warning", "scope": scope_name, "path": str(disabled_agents / item.name), "message": f"Conflicting state for agent `{item.name}`: active and disabled copies both exist."})
        if active_tasks.exists() and disabled_tasks.exists():
            for item in active_tasks.iterdir():
                if item.is_dir() and (disabled_tasks / item.name).exists():
                    diagnostics.append({"severity": "warning", "scope": scope_name, "path": str(disabled_tasks / item.name), "message": f"Conflicting state for task `{item.name}`: active and disabled copies both exist."})
        disabled_root = root / ".disabled"
        if disabled_root.exists():
            for item in disabled_root.iterdir():
                if item.name not in RESOURCE_TYPES:
                    diagnostics.append({"severity": "warning", "scope": scope_name, "path": str(item), "message": f"Orphaned entry under .disabled: `{item.name}`."})
        backup_root = root / ".backups"
        if backup_root.exists():
            for item in backup_root.iterdir():
                if not (item / "metadata.json").exists() or not (item / "snapshot").exists():
                    diagnostics.append({"severity": "warning", "scope": scope_name, "path": str(item), "message": f"Orphaned backup `{item.name}`."})
    if not diagnostics:
        diagnostics.append({"severity": "ok", "scope": scope, "path": "", "message": "No issues found."})
    return CommandResult(payload={"scope": scope, "diagnostics": diagnostics}, human_text=render_table(diagnostics, ["severity", "scope", "path", "message"]))


def mutate_directory_resource(ctx: AppContext, scope: str, item_type: str, item_id: str, enabled: bool, dry_run: bool = False) -> dict[str, Any]:
    root = scope_path(ctx, scope)
    make_backup(root, f"{('enable' if enabled else 'disable')} {item_type} {item_id}", dry_run=dry_run)
    return move_resource(root, item_type, item_id, "enable" if enabled else "disable", dry_run=dry_run)


def mutate_agent_or_task(ctx: AppContext, scope: str, item_type: str, item_id: str, enabled: bool, dry_run: bool = False) -> dict[str, Any]:
    root = scope_path(ctx, scope)
    make_backup(root, f"{('enable' if enabled else 'disable')} {item_type} {item_id}", dry_run=dry_run)
    return toggle_metadata_resource(root, item_type, item_id, enabled, dry_run=dry_run)


def mutate_command(ctx: AppContext, args: argparse.Namespace, enabled: bool) -> CommandResult:
    scope = resolve_write_scope(args, ctx)
    item_type = args.enable_type if enabled else args.disable_type
    item_id = args.id
    if item_type in {"skill", "memory"}:
        payload = mutate_directory_resource(ctx, scope, item_type, item_id, enabled, dry_run=args.dry_run)
    elif item_type in {"agent", "task"}:
        payload = mutate_agent_or_task(ctx, scope, item_type, item_id, enabled, dry_run=args.dry_run)
    else:
        root = scope_path(ctx, scope)
        make_backup(root, f"{('enable' if enabled else 'disable')} {item_type} {item_id}", dry_run=args.dry_run)
        payload = mutate_mcp(ctx, scope, item_type, item_id, enabled, dry_run=args.dry_run)
    human_text = f"{payload['action']}d {payload['type']} `{payload['id']}`"
    return CommandResult(payload={"scope": scope, "change": payload}, human_text=human_text)


def permission_command(ctx: AppContext, args: argparse.Namespace, allowed: bool) -> CommandResult:
    scope = resolve_write_scope(args, ctx)
    root = scope_path(ctx, scope)
    make_backup(root, f"{('allow' if allowed else 'deny')} skill {args.skill_id} for {args.agent_id}", dry_run=args.dry_run)
    payload = mutate_skill_permission(ctx, scope, args.agent_id, args.skill_id, allowed, dry_run=args.dry_run)
    return CommandResult(payload={"scope": scope, "change": payload}, human_text=f"{payload['action']}ed skill `{args.skill_id}` for agent `{args.agent_id}`")


def set_command(ctx: AppContext, args: argparse.Namespace) -> CommandResult:
    scope = resolve_write_scope(args, ctx)
    root = scope_path(ctx, scope)
    make_backup(root, f"set {args.set_type} {args.key}", dry_run=args.dry_run)
    payload = mutate_setting(ctx, scope, args.set_type, args.key, parse_value(args.value), dry_run=args.dry_run)
    return CommandResult(payload={"scope": scope, "change": payload}, human_text=f"Set {args.set_type} `{args.key}`")


def backup_command(ctx: AppContext, args: argparse.Namespace) -> CommandResult:
    scope = resolve_write_scope(args, ctx) if args.backup_type == "restore" else (args.scope or "workspace")
    root = scope_path(ctx, scope)
    if args.backup_type == "create":
        payload = make_backup(root, "manual backup", dry_run=args.dry_run)
        return CommandResult(payload={"scope": scope, "backup": payload}, human_text=f"Created backup `{payload['id']}`")
    payload = restore_backup(root, args.backup_id, dry_run=args.dry_run)
    return CommandResult(payload={"scope": scope, "restore": payload}, human_text=f"Restored backup `{args.backup_id}`")


def render_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not rows:
        return "(no results)"
    widths = {column: len(column) for column in columns}
    normalized = []
    for row in rows:
        normalized_row = {column: str(row.get(column, "")) for column in columns}
        normalized.append(normalized_row)
        for column, value in normalized_row.items():
            widths[column] = max(widths[column], len(value))
    header = " | ".join(column.ljust(widths[column]) for column in columns)
    divider = "-+-".join("-" * widths[column] for column in columns)
    body = [" | ".join(row[column].ljust(widths[column]) for column in columns) for row in normalized]
    return "\n".join([header, divider, *body])


def print_block(output_stream: TextIO, text: str = "") -> None:
    output_stream.write(text + "\n")


def safe_addnstr(window: Any, y: int, x: int, text: str, attr: int = 0) -> None:
    height, width = window.getmaxyx()
    if y < 0 or y >= height or x >= width:
        return
    available = max(0, width - x - 1)
    if available <= 0:
        return
    window.addnstr(y, x, text, available, attr)


def wrap_lines(text: str, width: int) -> list[str]:
    width = max(12, width)
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        if not paragraph:
            lines.append("")
            continue
        lines.extend(textwrap.wrap(paragraph, width=width, replace_whitespace=False, drop_whitespace=False) or [paragraph[:width]])
    return lines or [""]


def build_tui_categories() -> list[TuiCategory]:
    return [
        TuiCategory("skills", "Skills", "skill"),
        TuiCategory("agents", "Agents", "agent"),
        TuiCategory("tasks", "Tasks", "task"),
        TuiCategory("memories", "Memories", "memory"),
        TuiCategory("mcp-servers", "MCP Servers", "mcp-server"),
        TuiCategory("mcp-tools", "MCP Tools", "mcp-tool"),
    ]


def build_tui_browser_data(ctx: AppContext, scope: str) -> TuiBrowserData:
    categories = build_tui_categories()
    resources = collect_resources(ctx, scope)
    items_by_category: dict[str, list[dict[str, Any]]] = {
        "skills": sorted(resources["skills"], key=lambda item: item["id"]),
        "agents": sorted(resources["agents"], key=lambda item: item["id"]),
        "tasks": sorted(resources["tasks"], key=lambda item: item["id"]),
        "memories": sorted(resources["memories"], key=lambda item: item["id"]),
    }
    warnings: list[str] = []
    try:
        path, config = read_json_for_scope(ctx, scope, "mcp.json")
        items_by_category["mcp-servers"] = build_mcp_server_rows(path, config, scope)
        items_by_category["mcp-tools"] = build_mcp_tool_rows(path, config, scope)
    except CliError as exc:
        items_by_category["mcp-servers"] = []
        items_by_category["mcp-tools"] = []
        warnings.append(str(exc))
    return TuiBrowserData(categories=categories, items_by_category=items_by_category, warnings=warnings)


def tui_count_label(count: int, singular: str, plural: str | None = None) -> str:
    plural = plural or f"{singular}s"
    return f"{count} {singular if count == 1 else plural}"


def summarize_browser_counts(browser_data: TuiBrowserData) -> list[str]:
    counts = {category.key: len(browser_data.items_by_category.get(category.key, [])) for category in browser_data.categories}
    return [
        tui_count_label(counts.get("skills", 0), "skill"),
        tui_count_label(counts.get("agents", 0), "agent"),
        tui_count_label(counts.get("tasks", 0), "task"),
        tui_count_label(counts.get("mcp-servers", 0), "MCP server"),
        tui_count_label(counts.get("memories", 0), "memory", "memories"),
        tui_count_label(counts.get("mcp-tools", 0), "MCP tool"),
    ]


def clamp_tui_state(state: TuiState, browser_data: TuiBrowserData) -> None:
    if not browser_data.categories:
        state.selected_category_index = 0
        state.selected_item_index = 0
        state.focus = "categories"
        return
    state.selected_category_index = min(max(0, state.selected_category_index), len(browser_data.categories) - 1)
    items = browser_data.items_by_category.get(browser_data.categories[state.selected_category_index].key, [])
    if not items:
        state.selected_item_index = 0
        if state.focus == "items":
            state.focus = "categories"
        return
    state.selected_item_index = min(max(0, state.selected_item_index), len(items) - 1)


def current_tui_category(state: TuiState, browser_data: TuiBrowserData) -> TuiCategory:
    clamp_tui_state(state, browser_data)
    return browser_data.categories[state.selected_category_index]


def current_tui_items(state: TuiState, browser_data: TuiBrowserData) -> list[dict[str, Any]]:
    return browser_data.items_by_category.get(current_tui_category(state, browser_data).key, [])


def current_tui_item(state: TuiState, browser_data: TuiBrowserData) -> dict[str, Any] | None:
    items = current_tui_items(state, browser_data)
    if not items:
        return None
    return items[state.selected_item_index]


def is_item_enabled(item: dict[str, Any]) -> bool:
    return item.get("current_state") == "present"


def format_item_badge(item: dict[str, Any]) -> str:
    return "ON " if is_item_enabled(item) else "OFF"


def format_category_row(category: TuiCategory, browser_data: TuiBrowserData) -> str:
    count = len(browser_data.items_by_category.get(category.key, []))
    return f"{category.label} ({count})"


def format_item_row(item: dict[str, Any]) -> str:
    return f"[{format_item_badge(item)}] {item['id']}"


def category_item_label(category: TuiCategory, item: dict[str, Any]) -> str:
    item_type = str(item.get("type") or category.toggle_type).replace("-", " ")
    return item_type.title()


def describe_selected_item(category: TuiCategory, item: dict[str, Any] | None, browser_data: TuiBrowserData) -> str:
    if item is None:
        message = [
            f"{category.label}",
            "",
            "No items found in this category for the current scope.",
            "",
            "Use g / w / e or s to change scope.",
        ]
        if browser_data.warnings:
            message.extend(["", *browser_data.warnings])
        return "\n".join(message)
    lines = [
        f"{category_item_label(category, item)}: {item['id']}",
        f"State: {'enabled' if is_item_enabled(item) else 'disabled'} ({item.get('current_state', 'unknown')})",
        f"Scope: {item.get('scope', '')}",
    ]
    if item.get("source_path"):
        lines.append(f"Path: {item['source_path']}")
    if item.get("reason"):
        lines.append(f"Reason: {item['reason']}")
    lines.extend([
        "",
        "Actions:",
        "- Press t to toggle on/off",
        "- Press Enter to inspect",
        "- Press Tab or → to focus items, ← to go back",
    ])
    if browser_data.warnings:
        lines.extend(["", "Warnings:", *browser_data.warnings])
    return "\n".join(lines)


def build_toggle_command(category: TuiCategory, item: dict[str, Any]) -> list[str]:
    verb = "disable" if is_item_enabled(item) else "enable"
    return [verb, category.toggle_type, item["id"]]


def cycle_scope(scope: str) -> str:
    order = ["effective", "workspace", "global"]
    try:
        return order[(order.index(scope) + 1) % len(order)]
    except ValueError:
        return order[0]


def supports_rich_tui(input_fn: Callable[[str], str], output_stream: TextIO | None) -> bool:
    if input_fn is not input:
        return False
    target_output = output_stream or sys.stdout
    stdin_is_tty = getattr(sys.stdin, "isatty", lambda: False)()
    stdout_is_tty = getattr(target_output, "isatty", lambda: False)()
    return stdin_is_tty and stdout_is_tty and bool(os.environ.get("TERM"))


def is_mutating_command(command_args: list[str]) -> bool:
    return bool(command_args) and command_args[0] in MUTATING_COMMANDS


def run_command_for_interactive(
    command_args: list[str],
    *,
    ctx: AppContext,
    scope: str,
    dry_run: bool,
    env: dict[str, str] | None,
) -> CommandResult:
    full_args = [*interactive_scope_flag(scope)]
    if is_mutating_command(command_args) and dry_run:
        full_args.append("--dry-run")
    full_args.extend(command_args)
    return execute(full_args, cwd=ctx.cwd, env=env)


def prompt_text(input_fn: Callable[[str], str], prompt: str, *, allow_empty: bool = False) -> str | None:
    try:
        while True:
            value = input_fn(prompt).strip()
            if value or allow_empty:
                return value
            continue
    except EOFError:
        return None


def choose_option(
    input_fn: Callable[[str], str],
    output_stream: TextIO,
    title: str,
    options: list[tuple[str, str]],
    *,
    allow_back: bool = True,
) -> str | None:
    print_block(output_stream, title)
    for index, (_, label) in enumerate(options, start=1):
        print_block(output_stream, f"  {index}. {label}")
    if allow_back:
        print_block(output_stream, "  b. Back")
    while True:
        choice = prompt_text(input_fn, "Select an option: ")
        if choice is None:
            return None
        lowered = choice.lower()
        if allow_back and lowered in {"b", "back"}:
            return None
        if choice.isdigit():
            numeric = int(choice)
            if 1 <= numeric <= len(options):
                return options[numeric - 1][0]
        print_block(output_stream, "Invalid selection.")


def interactive_scope_flag(scope: str) -> list[str]:
    return [f"--{scope}"] if scope in {"global", "workspace", "effective"} else []


def interactive_write_scope(
    input_fn: Callable[[str], str],
    output_stream: TextIO,
    current_scope: str,
) -> str | None:
    if current_scope in {"global", "workspace"}:
        return current_scope
    return choose_option(
        input_fn,
        output_stream,
        "Mutating commands need a concrete target scope.",
        WRITE_SCOPE_OPTIONS,
    )


def run_prompt_interactive_command(
    command_args: list[str],
    *,
    ctx: AppContext,
    scope: str,
    dry_run: bool,
    input_fn: Callable[[str], str],
    output_stream: TextIO,
    env: dict[str, str] | None,
) -> None:
    mutating = command_args[0] in {"enable", "disable", "allow", "deny", "set", "backup"}
    target_scope = scope
    if mutating:
        resolved_scope = interactive_write_scope(input_fn, output_stream, scope)
        if not resolved_scope:
            return
        target_scope = resolved_scope
    try:
        result = run_command_for_interactive(command_args, ctx=ctx, scope=target_scope, dry_run=dry_run, env=env)
    except CliError as exc:
        print_block(output_stream, f"Error: {exc}")
        return
    print_block(output_stream)
    print_block(output_stream, result.human_text)
    print_block(output_stream)


def prompt_resource_action(
    input_fn: Callable[[str], str],
    output_stream: TextIO,
    verb: str,
) -> list[str] | None:
    resource_type = choose_option(
        input_fn,
        output_stream,
        f"Choose a resource type to {verb}:",
        RESOURCE_ACTION_OPTIONS,
    )
    if not resource_type:
        return None
    target_id = prompt_text(input_fn, f"Enter the {resource_type} id: ")
    if not target_id:
        return None
    return [verb, resource_type, target_id]


def prompt_list_action(input_fn: Callable[[str], str], output_stream: TextIO) -> list[str] | None:
    list_type = choose_option(
        input_fn,
        output_stream,
        "Choose what to list:",
        LIST_ACTION_OPTIONS,
    )
    return ["list", list_type] if list_type else None


def prompt_setting_action(input_fn: Callable[[str], str], output_stream: TextIO, verb: str) -> list[str] | None:
    key = prompt_text(input_fn, "Enter the key path: ")
    if not key:
        return None
    if verb == "get":
        return ["get", "setting", key]
    value = prompt_text(input_fn, "Enter the JSON value (for strings include quotes if desired): ")
    if value is None:
        return None
    return ["set", verb, key, value]


def prompt_skill_permission_action(
    input_fn: Callable[[str], str],
    output_stream: TextIO,
    verb: str,
) -> list[str] | None:
    skill_id = prompt_text(input_fn, "Enter the skill id: ")
    if not skill_id:
        return None
    agent_id = prompt_text(input_fn, "Enter the agent id: ")
    if not agent_id:
        return None
    return [verb, "skill", skill_id, "--agent", agent_id]


def prompt_backup_action(input_fn: Callable[[str], str], output_stream: TextIO) -> list[str] | None:
    choice = choose_option(
        input_fn,
        output_stream,
        "Backup actions:",
        BACKUP_ACTION_OPTIONS,
    )
    if not choice:
        return None
    if choice == "create":
        return ["backup", "create"]
    backup_id = prompt_text(input_fn, "Enter the backup id: ")
    if not backup_id:
        return None
    return ["backup", "restore", backup_id]


def run_prompt_interactive(
    *,
    args: argparse.Namespace,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    input_fn: Callable[[str], str] = input,
    output_stream: TextIO | None = None,
) -> int:
    if args.json_output:
        raise CliError("Interactive mode does not support --json. Run a subcommand instead.")
    output_stream = output_stream or sys.stdout
    ctx = build_context(cwd=cwd, env=env)
    current_scope = args.scope or "effective"
    session_dry_run = args.dry_run
    print_block(output_stream, "manage-dotagents interactive mode")
    print_block(output_stream, "Use the menu below to inspect and manage your .agents configuration.")
    while True:
        print_block(output_stream)
        print_block(output_stream, f"Current scope: {current_scope} | Dry-run: {'on' if session_dry_run else 'off'}")
        print_block(output_stream, "  1. Status overview")
        print_block(output_stream, "  2. List resources")
        print_block(output_stream, "  3. Show agent")
        print_block(output_stream, "  4. Enable resource")
        print_block(output_stream, "  5. Disable resource")
        print_block(output_stream, "  6. Allow skill for agent")
        print_block(output_stream, "  7. Deny skill for agent")
        print_block(output_stream, "  8. Get setting")
        print_block(output_stream, "  9. Set setting")
        print_block(output_stream, "  10. Set model")
        print_block(output_stream, "  11. Backups")
        print_block(output_stream, "  12. Doctor")
        print_block(output_stream, "  13. Diff")
        print_block(output_stream, "  14. Change scope")
        print_block(output_stream, "  15. Toggle dry-run")
        print_block(output_stream, "  q. Quit")
        choice = prompt_text(input_fn, "Choose an action: ")
        if choice is None:
            print_block(output_stream, "Exiting manage-dotagents.")
            return 0
        lowered = choice.lower()
        if lowered in {"q", "quit", "exit"}:
            print_block(output_stream, "Exiting manage-dotagents.")
            return 0
        command_args: list[str] | None = None
        if choice == "1":
            command_args = ["status"]
        elif choice == "2":
            command_args = prompt_list_action(input_fn, output_stream)
        elif choice == "3":
            agent_id = prompt_text(input_fn, "Enter the agent id: ")
            command_args = ["show", "agent", agent_id] if agent_id else None
        elif choice == "4":
            command_args = prompt_resource_action(input_fn, output_stream, "enable")
        elif choice == "5":
            command_args = prompt_resource_action(input_fn, output_stream, "disable")
        elif choice == "6":
            command_args = prompt_skill_permission_action(input_fn, output_stream, "allow")
        elif choice == "7":
            command_args = prompt_skill_permission_action(input_fn, output_stream, "deny")
        elif choice == "8":
            command_args = prompt_setting_action(input_fn, output_stream, "get")
        elif choice == "9":
            command_args = prompt_setting_action(input_fn, output_stream, "setting")
        elif choice == "10":
            command_args = prompt_setting_action(input_fn, output_stream, "model")
        elif choice == "11":
            command_args = prompt_backup_action(input_fn, output_stream)
        elif choice == "12":
            command_args = ["doctor"]
        elif choice == "13":
            command_args = ["diff"]
        elif choice == "14":
            new_scope = choose_option(
                input_fn,
                output_stream,
                "Choose a scope:",
                ALL_SCOPE_OPTIONS,
            )
            if new_scope:
                current_scope = new_scope
                print_block(output_stream, f"Scope changed to {current_scope}.")
            continue
        elif choice == "15":
            session_dry_run = not session_dry_run
            print_block(output_stream, f"Dry-run is now {'on' if session_dry_run else 'off'}.")
            continue
        else:
            print_block(output_stream, "Invalid selection.")
            continue
        if command_args:
            run_prompt_interactive_command(
                command_args,
                ctx=ctx,
                scope=current_scope,
                dry_run=session_dry_run,
                input_fn=input_fn,
                output_stream=output_stream,
                env=env,
            )


def curses_prompt_select(stdscr: Any, title: str, options: list[tuple[str, str]]) -> str | None:
    selected = 0
    while True:
        height, width = stdscr.getmaxyx()
        win_height = min(max(8, len(options) + 5), max(8, height - 4))
        win_width = min(max(44, len(title) + 6), max(44, width - 4))
        start_y = max(1, (height - win_height) // 2)
        start_x = max(1, (width - win_width) // 2)
        win = curses.newwin(win_height, win_width, start_y, start_x)
        win.keypad(True)
        win.box()
        safe_addnstr(win, 1, 2, title, curses.A_BOLD)
        safe_addnstr(win, 2, 2, "↑/↓ move • Enter select • Esc cancel")
        visible = max(1, win_height - 5)
        top = min(max(0, selected - visible + 1), max(0, len(options) - visible))
        for offset, (_, label) in enumerate(options[top : top + visible], start=0):
            index = top + offset
            attr = curses.A_REVERSE if index == selected else curses.A_NORMAL
            safe_addnstr(win, 4 + offset, 2, label, attr)
        win.refresh()
        key = win.getch()
        if key in {27, ord("q")}:
            return None
        if key in {curses.KEY_UP, ord("k")}:
            selected = (selected - 1) % len(options)
        elif key in {curses.KEY_DOWN, ord("j")}:
            selected = (selected + 1) % len(options)
        elif key in {10, 13, curses.KEY_ENTER}:
            return options[selected][0]


def curses_prompt_text(stdscr: Any, title: str, prompt: str) -> str | None:
    height, width = stdscr.getmaxyx()
    win_height = 8
    win_width = min(max(56, len(prompt) + 10), max(56, width - 4))
    start_y = max(1, (height - win_height) // 2)
    start_x = max(1, (width - win_width) // 2)
    win = curses.newwin(win_height, win_width, start_y, start_x)
    win.keypad(True)
    win.box()
    safe_addnstr(win, 1, 2, title, curses.A_BOLD)
    safe_addnstr(win, 2, 2, prompt)
    safe_addnstr(win, 3, 2, "Leave blank to cancel.")
    input_width = max(12, win_width - 6)
    input_win = curses.newwin(1, input_width, start_y + 5, start_x + 2)
    input_win.keypad(True)
    input_win.erase()
    input_win.refresh()
    try:
        curses.curs_set(1)
    except curses.error:
        pass
    curses.echo()
    try:
        raw = input_win.getstr(0, 0, input_width - 1)
    finally:
        curses.noecho()
        try:
            curses.curs_set(0)
        except curses.error:
            pass
    value = raw.decode("utf-8", errors="ignore").strip()
    return value or None


def resolve_tui_mutation_scope(stdscr: Any, current_scope: str) -> str | None:
    if current_scope in {"global", "workspace"}:
        return current_scope
    return curses_prompt_select(stdscr, "Choose a target scope for this change:", WRITE_SCOPE_OPTIONS)


def preferred_toggle_scope(current_scope: str, item: dict[str, Any]) -> str | None:
    if current_scope in {"global", "workspace"}:
        return current_scope
    item_scope = str(item.get("scope") or "")
    if item_scope in {"global", "workspace"}:
        return item_scope
    return None


def run_tui_utility_command(
    command_args: list[str],
    *,
    ctx: AppContext,
    scope: str,
    dry_run: bool,
    env: dict[str, str] | None,
) -> str:
    result = run_command_for_interactive(command_args, ctx=ctx, scope=scope, dry_run=dry_run, env=env)
    return result.human_text


def inspect_selected_item(
    state: TuiState,
    browser_data: TuiBrowserData,
    *,
    ctx: AppContext,
    env: dict[str, str] | None,
) -> str:
    category = current_tui_category(state, browser_data)
    item = current_tui_item(state, browser_data)
    if item is None:
        return describe_selected_item(category, item, browser_data)
    if category.key == "agents":
        result = run_command_for_interactive(["show", "agent", item["id"]], ctx=ctx, scope=state.scope, dry_run=state.dry_run, env=env)
        return result.human_text
    return describe_selected_item(category, item, browser_data)


def draw_box(window: Any, top: int, left: int, height: int, width: int, title: str, highlighted: bool = False) -> None:
    attr = curses.A_BOLD | (curses.A_REVERSE if highlighted else 0)
    window.addch(top, left, curses.ACS_ULCORNER)
    window.hline(top, left + 1, curses.ACS_HLINE, width - 2)
    window.addch(top, left + width - 1, curses.ACS_URCORNER)
    for row in range(top + 1, top + height - 1):
        window.addch(row, left, curses.ACS_VLINE)
        window.addch(row, left + width - 1, curses.ACS_VLINE)
    window.addch(top + height - 1, left, curses.ACS_LLCORNER)
    window.hline(top + height - 1, left + 1, curses.ACS_HLINE, width - 2)
    window.addch(top + height - 1, left + width - 1, curses.ACS_LRCORNER)
    safe_addnstr(window, top, left + 2, f" {title} ", attr)


def draw_tui(stdscr: Any, state: TuiState, browser_data: TuiBrowserData) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    if height < 20 or width < 90:
        safe_addnstr(stdscr, 1, 2, "Terminal too small for the rich TUI.", curses.A_BOLD)
        safe_addnstr(stdscr, 3, 2, "Resize the window or run in a wider terminal.")
        safe_addnstr(stdscr, 5, 2, "Press q to quit.")
        stdscr.refresh()
        return
    clamp_tui_state(state, browser_data)
    category = current_tui_category(state, browser_data)
    items = current_tui_items(state, browser_data)
    item = current_tui_item(state, browser_data)
    safe_addnstr(stdscr, 0, 2, "manage-dotagents", curses.A_BOLD)
    safe_addnstr(stdscr, 1, 2, f"Scope: {state.scope}   Dry-run: {'on' if state.dry_run else 'off'}   Status: {state.status_message}")
    safe_addnstr(stdscr, 3, 2, "Overview", curses.A_BOLD)
    overview_text = "   ".join(summarize_browser_counts(browser_data))
    for offset, line in enumerate(wrap_lines(overview_text, width - 4), start=0):
        safe_addnstr(stdscr, 4 + offset, 2, line)
    pane_top = 7
    pane_height = height - pane_top - 3
    left_width = 26
    middle_width = 34
    right_width = width - left_width - middle_width - 2
    draw_box(stdscr, pane_top, 0, pane_height, left_width, "Categories", highlighted=state.focus == "categories")
    draw_box(stdscr, pane_top, left_width, pane_height, middle_width, f"{category.label}", highlighted=state.focus == "items")
    draw_box(stdscr, pane_top, left_width + middle_width, pane_height, right_width, "Detail")
    category_visible = max(1, pane_height - 2)
    category_top = min(max(0, state.selected_category_index - category_visible + 1), max(0, len(browser_data.categories) - category_visible))
    for offset, category_entry in enumerate(browser_data.categories[category_top : category_top + category_visible], start=0):
        index = category_top + offset
        attr = curses.A_REVERSE if index == state.selected_category_index else curses.A_NORMAL
        safe_addnstr(stdscr, pane_top + 1 + offset, 1, format_category_row(category_entry, browser_data), attr)
    if items:
        item_visible = max(1, pane_height - 2)
        item_top = min(max(0, state.selected_item_index - item_visible + 1), max(0, len(items) - item_visible))
        for offset, item_entry in enumerate(items[item_top : item_top + item_visible], start=0):
            index = item_top + offset
            attr = curses.A_REVERSE if state.focus == "items" and index == state.selected_item_index else curses.A_NORMAL
            safe_addnstr(stdscr, pane_top + 1 + offset, left_width + 1, format_item_row(item_entry), attr)
    else:
        safe_addnstr(stdscr, pane_top + 2, left_width + 2, "No items in this scope.")
    detail_lines = wrap_lines(describe_selected_item(category, item, browser_data), right_width - 3)
    activity_lines = wrap_lines(state.last_output, right_width - 3)
    detail_space = max(4, (pane_height - 4) // 2)
    for offset, line in enumerate(detail_lines[:detail_space], start=0):
        safe_addnstr(stdscr, pane_top + 1 + offset, left_width + middle_width + 1, line)
    safe_addnstr(stdscr, pane_top + 1 + detail_space, left_width + middle_width + 1, "Recent activity", curses.A_BOLD)
    activity_space = max(1, pane_height - detail_space - 4)
    for offset, line in enumerate(activity_lines[:activity_space], start=0):
        safe_addnstr(stdscr, pane_top + 2 + detail_space + offset, left_width + middle_width + 1, line)
    stdscr.hline(height - 3, 0, curses.ACS_HLINE, width)
    footer = "↑/↓ move  Tab/←/→ switch pane  Enter inspect  t toggle  r refresh  o status  c doctor  f diff  s scope  d dry-run  q quit"
    safe_addnstr(stdscr, height - 2, 2, footer)
    stdscr.refresh()


def run_curses_tui(args: argparse.Namespace, *, cwd: Path | None = None, env: dict[str, str] | None = None) -> int:
    ctx = build_context(cwd=cwd, env=env)
    state = TuiState(scope=args.scope or "effective", dry_run=args.dry_run)
    browser_data = build_tui_browser_data(ctx, state.scope)

    def _app(stdscr: Any) -> int:
        nonlocal browser_data
        try:
            curses.use_default_colors()
        except curses.error:
            pass
        stdscr.keypad(True)
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        while True:
            clamp_tui_state(state, browser_data)
            draw_tui(stdscr, state, browser_data)
            key = stdscr.getch()
            if key in {ord("q"), 27}:
                state.status_message = "Bye"
                return 0
            if key in {curses.KEY_UP, ord("k")}:
                if state.focus == "categories":
                    state.selected_category_index = (state.selected_category_index - 1) % len(browser_data.categories)
                    state.selected_item_index = 0
                else:
                    items = current_tui_items(state, browser_data)
                    if items:
                        state.selected_item_index = (state.selected_item_index - 1) % len(items)
                continue
            if key in {curses.KEY_DOWN, ord("j")}:
                if state.focus == "categories":
                    state.selected_category_index = (state.selected_category_index + 1) % len(browser_data.categories)
                    state.selected_item_index = 0
                else:
                    items = current_tui_items(state, browser_data)
                    if items:
                        state.selected_item_index = (state.selected_item_index + 1) % len(items)
                continue
            if key in {9, curses.KEY_RIGHT, ord("l")}:
                if current_tui_items(state, browser_data):
                    state.focus = "items"
                    state.status_message = f"Browsing {current_tui_category(state, browser_data).label}"
                continue
            if key in {curses.KEY_LEFT, ord("h")}:
                state.focus = "categories"
                continue
            if key == ord("s"):
                state.scope = cycle_scope(state.scope)
                state.status_message = f"Scope set to {state.scope}"
                browser_data = build_tui_browser_data(ctx, state.scope)
                continue
            if key == ord("d"):
                state.dry_run = not state.dry_run
                state.status_message = f"Dry-run {'enabled' if state.dry_run else 'disabled'}"
                continue
            if key == ord("g"):
                state.scope = "global"
                state.status_message = "Scope set to global"
                browser_data = build_tui_browser_data(ctx, state.scope)
                continue
            if key == ord("w"):
                state.scope = "workspace"
                state.status_message = "Scope set to workspace"
                browser_data = build_tui_browser_data(ctx, state.scope)
                continue
            if key == ord("e"):
                state.scope = "effective"
                state.status_message = "Scope set to effective"
                browser_data = build_tui_browser_data(ctx, state.scope)
                continue
            if key == ord("r"):
                browser_data = build_tui_browser_data(ctx, state.scope)
                state.status_message = "Refreshed"
                continue
            if key == ord("o"):
                try:
                    state.last_output = run_tui_utility_command(["status"], ctx=ctx, scope=state.scope, dry_run=state.dry_run, env=env)
                    state.status_message = "Loaded status overview"
                except CliError as exc:
                    state.last_output = f"Error: {exc}"
                    state.status_message = "Error"
                continue
            if key == ord("c"):
                try:
                    state.last_output = run_tui_utility_command(["doctor"], ctx=ctx, scope=state.scope, dry_run=state.dry_run, env=env)
                    state.status_message = "Doctor complete"
                except CliError as exc:
                    state.last_output = f"Error: {exc}"
                    state.status_message = "Error"
                continue
            if key == ord("f"):
                try:
                    state.last_output = run_tui_utility_command(["diff"], ctx=ctx, scope=state.scope, dry_run=state.dry_run, env=env)
                    state.status_message = "Diff complete"
                except CliError as exc:
                    state.last_output = f"Error: {exc}"
                    state.status_message = "Error"
                continue
            if key == ord("t"):
                item = current_tui_item(state, browser_data)
                if item is None:
                    state.status_message = "No item selected"
                    continue
                category = current_tui_category(state, browser_data)
                command_args = build_toggle_command(category, item)
                target_scope = preferred_toggle_scope(state.scope, item) or state.scope
                if is_mutating_command(command_args) and target_scope not in {"global", "workspace"}:
                    resolved_scope = resolve_tui_mutation_scope(stdscr, state.scope)
                    if not resolved_scope:
                        state.status_message = "Cancelled"
                        continue
                    target_scope = resolved_scope
                try:
                    result = run_command_for_interactive(command_args, ctx=ctx, scope=target_scope, dry_run=state.dry_run, env=env)
                    state.last_output = result.human_text
                    state.status_message = f"Toggled {item['id']}"
                    browser_data = build_tui_browser_data(ctx, state.scope)
                except CliError as exc:
                    state.last_output = f"Error: {exc}"
                    state.status_message = "Error"
                continue
            if key not in {10, 13, curses.KEY_ENTER}:
                continue
            if state.focus == "categories":
                if current_tui_items(state, browser_data):
                    state.focus = "items"
                    state.status_message = f"Opened {current_tui_category(state, browser_data).label}"
                else:
                    state.status_message = "No items in this category"
                continue
            try:
                state.last_output = inspect_selected_item(state, browser_data, ctx=ctx, env=env)
                state.status_message = "Item details loaded"
            except CliError as exc:
                state.last_output = f"Error: {exc}"
                state.status_message = "Error"
        return 0

    return int(curses.wrapper(_app))


def run_interactive(
    *,
    args: argparse.Namespace,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    input_fn: Callable[[str], str] = input,
    output_stream: TextIO | None = None,
) -> int:
    if args.json_output:
        raise CliError("Interactive mode does not support --json. Run a subcommand instead.")
    if supports_rich_tui(input_fn, output_stream):
        return run_curses_tui(args, cwd=cwd, env=env)
    return run_prompt_interactive(args=args, cwd=cwd, env=env, input_fn=input_fn, output_stream=output_stream)


def dispatch(args: argparse.Namespace, ctx: AppContext) -> CommandResult:
    command = args.command
    if command == "status":
        return status_command(ctx, resolve_read_scope(args, ctx))
    if command == "list":
        scope = resolve_read_scope(args, ctx)
        return list_command(ctx, scope, args.list_type)
    if command == "get":
        return get_setting_command(ctx, resolve_read_scope(args, ctx), args.key)
    if command == "show":
        return show_agent_command(ctx, resolve_read_scope(args, ctx), args.id)
    if command == "doctor":
        return doctor_command(ctx, resolve_read_scope(args, ctx))
    if command == "diff":
        return diff_command(ctx)
    if command == "enable":
        return mutate_command(ctx, args, True)
    if command == "disable":
        return mutate_command(ctx, args, False)
    if command == "allow":
        return permission_command(ctx, args, True)
    if command == "deny":
        return permission_command(ctx, args, False)
    if command == "set":
        return set_command(ctx, args)
    if command == "backup":
        return backup_command(ctx, args)
    raise CliError(f"Unsupported command `{command}`.")


def execute(argv: list[str] | None = None, *, cwd: Path | None = None, env: dict[str, str] | None = None) -> CommandResult:
    parser = build_parser(require_command=True)
    args = parser.parse_args(argv)
    ctx = build_context(cwd=cwd, env=env)
    return dispatch(args, ctx)


def main(
    argv: list[str] | None = None,
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    input_fn: Callable[[str], str] = input,
    output_stream: TextIO | None = None,
) -> int:
    try:
        parser = build_parser(require_command=False)
        args = parser.parse_args(argv)
        if not args.command:
            return run_interactive(args=args, cwd=cwd, env=env, input_fn=input_fn, output_stream=output_stream)
        result = dispatch(args, build_context(cwd=cwd, env=env))
        output = json.dumps(result.payload, indent=2, sort_keys=True) if args.json_output else result.human_text
        print_block(output_stream or sys.stdout, output)
        return result.exit_code
    except CliError as exc:
        print_block(output_stream or sys.stdout, f"Error: {exc}")
        return 1
