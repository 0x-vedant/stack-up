import logging
from typing import List

logger = logging.getLogger(__name__)

# [NEW METHOD ONLY] - Priority 4
def inject_mcp_tools(task_object: "Task", mcp_artifact_id: str, manifest: dict) -> "Task":
    """
    Priority 4: Zero-Code Injection.
    Dynamically injects MCP tools into a CrewAI Task at runtime, 
    overriding the agent tools without modifying user source code.
    """
    from .utils.mcp_tools import MCPCrewTool
    
    if not hasattr(task_object, "tools") or task_object.tools is None:
        task_object.tools = []
        
    for tool_def in manifest.get("tools", []):
        tool_name = tool_def.get("name")
        tool_desc = tool_def.get("description", "MCP proxied tool")
        
        # Inject the proxy wrapper as a CrewAI BaseTool
        proxy_tool = MCPCrewTool(
            name=tool_name,
            description=tool_desc,
            artifact_id=mcp_artifact_id,
            tool_name_remote=tool_name
        )
        task_object.tools.append(proxy_tool)
        logger.info(f"Dynamically injected MCP tool '{tool_name}' into Task.")
        
    return task_object
