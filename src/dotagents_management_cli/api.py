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
            "description": f"Skill in {s['scope']} scope"
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
