from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotagents_management_cli.cli import build_context, collect_resources, read_json_for_scope, build_mcp_server_rows

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
        agents.append({
            "id": a["id"],
            "name": a["id"],
            "type": "task-loop",
            "status": "in-progress" if a["current_state"] == "present" else "idle"
        })

    skills = []
    for s in resources.get("skills", []):
        skills.append({
            "id": s["id"],
            "name": s["id"],
            "description": f"Skill in {s['scope']} scope",
            "status": "active" if s["current_state"] == "present" else "inactive"
        })

    tasks = []
    for t in resources.get("tasks", []):
        tasks.append({
            "id": t["id"],
            "title": t["id"].replace("-", " ").title(),
            "status": "in_progress" if t["current_state"] == "present" else "not_started",
            "agent": None
        })

    memories = []
    for m in resources.get("memories", []):
        memories.append({
            "id": m["id"],
            "name": m["id"].replace("-", " ").title(),
            "size": "? KB",
            "status": "active" if m["current_state"] == "present" else "archived"
        })

    path, mcp_config = read_json_for_scope(ctx, "effective", "mcp.json")
    mcp_rows = build_mcp_server_rows(path, mcp_config, "effective")

    mcp_servers = []
    for m in mcp_rows:
        mcp_servers.append({
            "id": m["id"],
            "name": m["id"],
            "status": "connected" if m["current_state"] == "present" else "disconnected"
        })

    return {
        "agents": agents,
        "skills": skills,
        "tasks": tasks,
        "mcpServers": mcp_servers,
        "memories": memories
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
