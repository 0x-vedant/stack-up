import json
from typing import Any, Dict, Optional, Type
import httpx
from pydantic import BaseModel, Field

# --- LangChain ---
try:
    from langchain_core.tools import StructuredTool
    from langchain_core.callbacks import CallbackManagerForToolRun, AsyncCallbackManagerForToolRun
except ImportError:
    StructuredTool = object
    CallbackManagerForToolRun = None
    AsyncCallbackManagerForToolRun = None

# --- CrewAI ---
try:
    from crewai.tools import BaseTool
except ImportError:
    class BaseTool(BaseModel):
        name: str
        description: str
        args_schema: Optional[Type[BaseModel]] = None

class AgentCallError(Exception):
    pass

def execute_bridge_call(artifact_id: str, tool_name: str, arguments: dict, bridge_url: str = "http://localhost:8000") -> str:
    url = f"{bridge_url.rstrip('/')}/mcp/{artifact_id}/call"
    headers = {"Content-Type": "application/json"}
    
    try:
        resp = httpx.post(
            url,
            json={"tool_name": tool_name, "arguments": arguments},
            headers=headers,
            timeout=30.0
        )
        resp.raise_for_status()
        result = resp.json()
        
        content_arr = result.get("result", {}).get("content", [])
        if content_arr and isinstance(content_arr, list):
            return content_arr[0].get("text", str(content_arr))
        return json.dumps(result)
        
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status == 500:
            raise AgentCallError(f"Agent failed to execute tool. Subprocess may be dead. Details: {e.response.text}")
        raise AgentCallError(f"Bridge HTTP Error ({status}): {e.response.text}")
    except httpx.RequestError as e:
        raise AgentCallError(f"Network error connecting to bridge: {str(e)}")

def create_mcp_http_tool(artifact_id: str, tool_name: str, tool_desc: str, schema: Type[BaseModel]) -> StructuredTool:
    def _run_mcp_tool(*args, **kwargs) -> str:
        return execute_bridge_call(artifact_id, tool_name, kwargs)

    return StructuredTool.from_function(
        func=_run_mcp_tool,
        name=tool_name,
        description=tool_desc,
        args_schema=schema,
    )

class MCPCrewTool(BaseTool):
    artifact_id: str = Field(..., description="ID of the target R1/R2 agent bridge")
    tool_name_remote: str = Field(..., description="The original tool name registered in the MCP Manifest")
    
    def _run(self, *args, **kwargs) -> str:
        return execute_bridge_call(self.artifact_id, self.tool_name_remote, kwargs)
