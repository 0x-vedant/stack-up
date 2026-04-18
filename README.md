# Nasiko MCP Platform

Nasiko is an AI-agent and MCP server registry with orchestration, observability, and zero-code tool injection.

## Architecture

```
Upload (.zip)
    |
    v
R1 Ingestion ── detect artifact type (agent vs MCP server)
    |
    v
R3 Manifest ── parse @mcp.tool / @mcp.resource / @mcp.prompt
    |
    v
R2 Bridge ── spawn subprocess, MCP JSON-RPC handshake, HTTP proxy
    |
    v
R4 Orchestrator ── zero-code tool injection into agents
    |
    v
R5 Observability ── OpenTelemetry spans in Arize Phoenix
```

### Components

| Component | Path | Purpose |
|---|---|---|
| **R1 Ingestion** | `nasiko/app/ingestion/` | Upload validation, AST-based framework detection |
| **R2 Bridge** | `nasiko/mcp_bridge/` | STDIO-to-HTTP bridge, Kong routing, subprocess management |
| **R3 Manifest** | `R3/` | Static parser for MCP tools, resources, prompts |
| **R4 Orchestrator** | `nasiko/app/` | Agent builder, MCP linker, Redis listener, state management |
| **R5 Observability** | `nasiko/app/utils/observability/` | OpenTelemetry tracing for MCP bridge |

---

## How to Publish an MCP Server

### 1. Write your MCP server

Use the official Python MCP SDK:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("my-server")

@mcp.tool()
def calculate(expression: str) -> str:
    """Evaluate a math expression."""
    return str(eval(expression))

@mcp.resource("config://settings")
def get_config() -> str:
    """Return app configuration."""
    return '{"debug": false}'

@mcp.prompt()
def explain(topic: str) -> str:
    """Generate an explanation prompt."""
    return f"Explain {topic} in simple terms"
```

### 2. Package and upload

```bash
# Zip your project
zip -r my-mcp-server.zip server.py requirements.txt

# Upload to Nasiko
curl -X POST http://localhost:8000/ingest \
  -F "file=@my-mcp-server.zip"
```

The platform will:
- Detect it as an MCP server (via `mcp`/`fastmcp` imports)
- Auto-generate a manifest with your tools, resources, and prompts
- Return an `artifact_id` for association

### 3. What gets auto-generated

The manifest at `/tmp/nasiko/{artifact_id}/manifest.json` contains:

```json
{
  "artifact_id": "abc-123",
  "tools": [
    {
      "name": "calculate",
      "description": "Evaluate a math expression.",
      "input_schema": {
        "type": "object",
        "properties": {"expression": {"type": "string"}},
        "required": ["expression"]
      }
    }
  ],
  "resources": [
    {"uri": "config://settings", "name": "get_config", "description": "Return app configuration."}
  ],
  "prompts": [
    {
      "name": "explain",
      "description": "Generate an explanation prompt.",
      "input_schema": {
        "type": "object",
        "properties": {"topic": {"type": "string"}},
        "required": ["topic"]
      }
    }
  ]
}
```

---

## How to Consume an MCP Server from an Agent

### Zero-code association

Existing LangChain/CrewAI agents can consume published MCP tools **without code changes**:

```python
from nasiko.app.agent_builder import inject_mcp_tools

# Load the manifest (auto-generated at upload time)
manifest = load_manifest("mcp-artifact-id")

# Inject tools into a CrewAI task — no agent code changes needed
inject_mcp_tools(task, "mcp-artifact-id", manifest)
```

This dynamically creates typed Pydantic schemas and wires HTTP proxy tools that forward calls through the R2 bridge to the running MCP subprocess.

### What happens under the hood

1. `inject_mcp_tools()` reads the manifest's tool definitions
2. For each tool, it creates a `MCPCrewTool` with a dynamically generated Pydantic schema
3. The tool's `_run()` method calls `execute_bridge_call()` which POSTs to `/mcp/{id}/call`
4. The R2 bridge forwards the call via JSON-RPC over STDIO to the MCP subprocess
5. W3C `traceparent` headers are forwarded for end-to-end observability

---

## Validation Rules

| Scenario | Result |
|---|---|
| Single framework detected (`mcp`, `langchain`, or `crewai`) | 200 OK with `IngestionRecord` |
| No recognized framework imports | 422 `AMBIGUOUS_ARTIFACT` |
| Multiple frameworks in same project | 422 `AMBIGUOUS_ARTIFACT` |
| Non-zip file uploaded | 400 Bad Request |
| ZipSlip path traversal detected | 400 Bad Request |

---

## Running Tests

```bash
# Install dependencies
pip install fastapi httpx pydantic tenacity pytest python-multipart

# Run all tests (76 total)
PYTHONPATH=. pytest tests/ -v
```

### Test Suites

| Suite | Tests | Coverage |
|---|---|---|
| `tests/bridge/test_bridge_server.py` | 40 | MCP handshake, subprocess, port scanning, AST constraints |
| `tests/bridge/test_kong_registrar.py` | 3 | Kong service/route registration |
| `tests/integration/test_mcp_e2e.py` | 4 | Gateway env vars, linker endpoint, type mapping |
| `tests/orchestration/test_mcp_linker.py` | 4 | Linker validation, tool injection |
| `tests/track1/test_track1_integration.py` | 25 | Full Track 1: upload, detection, ambiguity, manifest |

---

## Local Development

```bash
# Start the platform with LLM gateway
docker-compose -f nasiko/docker-compose.local.yml up

# The LLM gateway runs at http://llm-gateway:4000
# Agents use env vars OPENAI_API_BASE and OPENAI_API_KEY injected by the platform
```

## Entry Points

| Endpoint | Method | Purpose |
|---|---|---|
| `/ingest` | POST | Upload and detect artifact (zip file) |
| `/mcp/{id}/start` | POST | Start MCP bridge subprocess |
| `/mcp/{id}/health` | GET | Check bridge subprocess health |
| `/mcp/{id}/call` | POST | Proxy tool call to MCP subprocess |
| `/agent/link` | POST | Associate agent to MCP server |
| `/manifest/generate` | POST | Generate MCP manifest from source |
| `/manifest/{id}` | GET | Retrieve generated manifest |