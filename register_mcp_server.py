#!/usr/bin/env python3
"""Register an MCP server in the Nasiko platform registry.

This script:
1. Authenticates with the Nasiko auth service
2. Registers an MCP server as a registry entry with skills (tools)
3. The MCP server then appears in the web app's agent/server list
"""
import httpx
import json
import sys
from datetime import datetime, timezone

AUTH_URL = "http://localhost:8082"
BACKEND_URL = "http://localhost:8000"

# Step 1: Get auth token
print("[1/3] Authenticating...")
resp = httpx.post(f"{AUTH_URL}/auth/users/login", json={
    "access_key": "NASK_I-xM-dIVbDu9JU00IlZNuQ",
    "access_secret": "WnF7Wra-cAHJq-jVxljMNFFonKUoCSSqu-mQIzszHF0",
})
if resp.status_code != 200:
    print(f"Auth failed: {resp.status_code} {resp.text}")
    sys.exit(1)

token = resp.json()["token"]
print(f"  ✅ Got JWT token (super_user={resp.json().get('is_super_user')})")

headers = {"Authorization": f"Bearer {token}"}

# Step 2: Get user info for owner_id
print("[2/3] Getting user info...")
user_resp = httpx.get(f"{AUTH_URL}/auth/user", headers=headers)
print(f"  User endpoint: {user_resp.status_code}")
if user_resp.status_code == 200:
    user_data = user_resp.json()
    owner_id = user_data.get("id", user_data.get("_id", user_data.get("user_id", "superuser")))
    print(f"  ✅ Owner ID: {owner_id}")
    print(f"  User data keys: {list(user_data.keys())}")
else:
    owner_id = "superuser"
    print(f"  ⚠️ Using fallback owner_id: {owner_id}")
    print(f"  Response: {user_resp.text[:200]}")

# Step 3: Register MCP server in registry
print("[3/3] Registering MCP server in registry...")
now = datetime.now(timezone.utc).isoformat()

registry_entry = {
    "id": "mcp-hello-world-server",
    "name": "MCP Hello World Server",
    "description": "A demo MCP server that provides hello_world and calculator tools. Published via Nasiko's STDIO-to-HTTP bridge with auto-generated manifest.",
    "url": "http://kong-gateway:8000/mcp/mcp-hello-world-server",
    "preferredTransport": "JSONRPC",
    "version": "1.0.0",
    "provider": {
        "organization": "Team Stack-Up (Track 1)",
    },
    "capabilities": {
        "streaming": False,
        "pushNotifications": False,
        "stateTransitionHistory": False,
        "chat_agent": False,
    },
    "skills": [
        {
            "id": "hello_world",
            "name": "hello_world",
            "description": "Returns a greeting for the given name. Input: {name: string}",
            "tags": ["mcp", "greeting", "demo"],
        },
        {
            "id": "add",
            "name": "add",
            "description": "Adds two numbers together. Input: {a: number, b: number}",
            "tags": ["mcp", "calculator", "math"],
        },
    ],
    "tags": ["mcp-server", "stdio", "track1", "auto-published"],
    "owner_id": owner_id,
    "created_at": now,
    "updated_at": now,
}

resp = httpx.post(
    f"{BACKEND_URL}/api/v1/registry",
    json=registry_entry,
    headers=headers,
)
print(f"  Registry response: {resp.status_code}")
if resp.status_code in (200, 201):
    print(f"  ✅ MCP server registered successfully!")
    print(f"  Response: {json.dumps(resp.json(), indent=2)[:500]}")
else:
    print(f"  ❌ Failed: {resp.text[:500]}")

# Step 4: Verify it appears in the list
print("\n[Verify] Listing registered agents...")
list_resp = httpx.get(f"{BACKEND_URL}/api/v1/registry/user/agents", headers=headers)
print(f"  List response: {list_resp.status_code}")
if list_resp.status_code == 200:
    data = list_resp.json()
    if isinstance(data, dict) and "data" in data:
        agents = data["data"]
    elif isinstance(data, list):
        agents = data
    else:
        agents = [data]
    print(f"  Found {len(agents)} registered agent(s):")
    for a in agents:
        name = a.get("name", "?")
        aid = a.get("id", "?")
        tags = a.get("tags", [])
        print(f"    - {name} (id={aid}) tags={tags}")
