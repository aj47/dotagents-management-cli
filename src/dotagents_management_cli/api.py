from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotagents_management_cli.cli import (
    build_context, collect_resources, read_json_for_scope, build_mcp_server_rows,
    TARGET_REGISTRY, mutate_directory_resource, mutate_agent_or_task, mutate_mcp,
    load_json_object, build_skill_availability, parse_frontmatter, mutate_skill_permission,
    target_permission_command
)
from pathlib import Path
import argparse

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/resources")
def get_resources():
    ctx = build_context()
    resources = collect_resources(ctx, "effective")

    agents = []
    for a in resources.get("agents", []):
        try:
            config_path = Path(a["source_path"]) / "config.json"
            config = load_json_object(config_path, create_default=True) if config_path.exists() else {}
            allowed_skills = [
                s["id"] for s in resources.get("skills", [])
                if build_skill_availability(s, config)["available"]
            ]
        except Exception:
            allowed_skills = []

        agents.append({
            "id": a["id"],
            "name": a["id"],
            "type": "agent",
            "scope": a["scope"],
            "status": "in-progress" if a["current_state"] == "present" else "idle",
            "is_symlink": a.get("is_symlink", False),
            "allowed_skills": allowed_skills
        })

    skills = []
    for s in resources.get("skills", []):
        try:
            skill_dir = Path(s["source_path"])
            skill_doc_path = None
            for name in ("SKILL.md", "skill.md", "README.md"):
                candidate = skill_dir / name
                if candidate.exists():
                    skill_doc_path = candidate
                    break
            if skill_doc_path:
                meta, _ = parse_frontmatter(skill_doc_path)
                targets = meta.get("allowed_targets")
                if isinstance(targets, list):
                    allowed_targets = targets
                else:
                    allowed_targets = [t for t in TARGET_REGISTRY.keys() if t != "dummy"]
            else:
                allowed_targets = [t for t in TARGET_REGISTRY.keys() if t != "dummy"]
        except Exception:
            allowed_targets = [t for t in TARGET_REGISTRY.keys() if t != "dummy"]

        skills.append({
            "id": s["id"],
            "name": s["id"],
            "description": f"Skill in {s['scope']} scope",
            "scope": s["scope"],
            "type": "skill",
            "status": "active" if s["current_state"] == "present" else "inactive",
            "is_symlink": s.get("is_symlink", False),
            "allowed_targets": allowed_targets
        })

    tasks = []
    for t in resources.get("tasks", []):
        tasks.append({
            "id": t["id"],
            "title": t["id"].replace("-", " ").title(),
            "scope": t["scope"],
            "type": "task",
            "status": "in_progress" if t["current_state"] == "present" else "not_started",
            "agent": None,
            "is_symlink": t.get("is_symlink", False)
        })

    memories = []
    for m in resources.get("memories", []):
        memories.append({
            "id": m["id"],
            "name": m["id"].replace("-", " ").title(),
            "size": "? KB",
            "scope": m["scope"],
            "type": "memory",
            "status": "active" if m["current_state"] == "present" else "archived",
            "is_symlink": m.get("is_symlink", False)
        })

    path, mcp_config = read_json_for_scope(ctx, "effective", "mcp.json")
    mcp_rows = build_mcp_server_rows(path, mcp_config, "effective")

    mcp_servers = []
    for m in mcp_rows:
        mcp_servers.append({
            "id": m["id"],
            "name": m["id"],
            "scope": m["scope"],
            "type": "mcp-server",
            "status": "connected" if m["current_state"] == "present" else "disconnected",
            "is_symlink": False
        })

    targets = []
    for target_id, adapter_cls in TARGET_REGISTRY.items():
        if target_id == "dummy":
            continue
        adapter = adapter_cls()
        is_unsynced = False
        try:
            is_unsynced = adapter.check_drift(ctx, "effective")
        except Exception:
            pass

        targets.append({
            "id": target_id,
            "name": target_id.replace("-", " ").title(),
            "type": "target",
            "status": "unsynced" if is_unsynced else "synced",
        })

    return {
        "agents": agents,
        "skills": skills,
        "tasks": tasks,
        "mcpServers": mcp_servers,
        "memories": memories,
        "targets": targets
    }

from fastapi import HTTPException
from dotagents_management_cli.cli import mutate_directory_resource, mutate_agent_or_task, mutate_mcp

@app.post("/api/resources/{resource_type}/{resource_id}/{action}")
def mutate_resource(resource_type: str, resource_id: str, action: str):
    if action not in ("enable", "disable"):
        raise HTTPException(status_code=400, detail="Invalid action")

    enabled = action == "enable"
    ctx = build_context()

    # Try to find the resource's current scope
    found_scope = None
    if resource_type == "mcp-server":
        path, mcp_config = read_json_for_scope(ctx, "effective", "mcp.json")
        mcp_rows = build_mcp_server_rows(path, mcp_config, "effective")
        for r in mcp_rows:
            if r["id"] == resource_id:
                found_scope = r["scope"]
                break
    else:
        resources = collect_resources(ctx, "effective")
        plural_type = "memories" if resource_type == "memory" else resource_type + "s"
        for r in resources.get(plural_type, []):
            if r["id"] == resource_id:
                found_scope = r["scope"]
                break

    if not found_scope:
        found_scope = "workspace" # Default to workspace if unknown

    try:
        if resource_type in ("skill", "memory"):
            mutate_directory_resource(ctx, found_scope, resource_type, resource_id, enabled)
        elif resource_type in ("agent", "task"):
            mutate_agent_or_task(ctx, found_scope, resource_type, resource_id, enabled)
        elif resource_type == "mcp-server":
            mutate_mcp(ctx, found_scope, resource_type, resource_id, enabled)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported resource type {resource_type}")

        # Optional: trigger auto sync if we wanted to
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"status": "success", "action": action, "resource_type": resource_type, "resource_id": resource_id}

@app.post("/api/resources/agent/{agent_id}/skill/{skill_id}/{action}")
def mutate_agent_skill(agent_id: str, skill_id: str, action: str):
    if action not in ("allow", "deny"):
        raise HTTPException(status_code=400, detail="Invalid action")
    ctx = build_context()
    resources = collect_resources(ctx, "effective")
    found_scope = None
    for a in resources.get("agents", []):
        if a["id"] == agent_id:
            found_scope = a["scope"]
            break
    if not found_scope:
        found_scope = "workspace"
    try:
        mutate_skill_permission(ctx, found_scope, agent_id, skill_id, action == "allow")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "success", "action": action, "agent_id": agent_id, "skill_id": skill_id}

@app.post("/api/resources/skill/{skill_id}/target/{target_id}/{action}")
def mutate_skill_target(skill_id: str, target_id: str, action: str):
    if action not in ("allow", "deny"):
        raise HTTPException(status_code=400, detail="Invalid action")
    ctx = build_context()
    resources = collect_resources(ctx, "effective")
    found_scope = None
    for s in resources.get("skills", []):
        if s["id"] == skill_id:
            found_scope = s["scope"]
            break
    if not found_scope:
        found_scope = "workspace"

    try:
        args = argparse.Namespace(target_id=target_id, skill_id=skill_id, dry_run=False)
        target_permission_command(ctx, args, found_scope, action == "allow")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "success", "action": action, "skill_id": skill_id, "target_id": target_id}

from dotagents_management_cli.cli import TARGET_REGISTRY

@app.post("/api/sync")
def sync_all():
    ctx = build_context()
    results = {}
    for target_id, adapter_cls in TARGET_REGISTRY.items():
        try:
            adapter_cls().export_to_target(ctx, "workspace", False)
            results[target_id] = "success"
        except Exception as e:
            results[target_id] = str(e)
    return {"status": "success", "results": results}


@app.post("/api/sync/{target_id}")
def sync_target(target_id: str):
    if target_id not in TARGET_REGISTRY:
        raise HTTPException(status_code=400, detail=f"Unknown target {target_id}")

    ctx = build_context()
    try:
        adapter = TARGET_REGISTRY[target_id]()
        adapter.export_to_target(ctx, "workspace", False)
        return {"status": "success", "target_id": target_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))