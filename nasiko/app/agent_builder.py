import logging
import os
from pydantic import BaseModel, create_model, Field as PydanticField

logger = logging.getLogger(__name__)

# [NEW METHOD ONLY] - Track 1.5 / LLM Gateway Injection Hook
def get_gateway_env_vars() -> dict:
    """
    Returns the required environment overrides to force uploaded agents 
    (LangChain/CrewAI) to use the Nasiko internal LiteLLM proxy instead 
    of parsing their ZIP files for hardcoded API keys.
    """
    return {
        "OPENAI_API_BASE": "http://llm-gateway:4000",
        "OPENAI_BASE_URL": "http://llm-gateway:4000",
        "OPENAI_API_KEY": "nasiko-virtual-proxy-key",
        "ANTHROPIC_API_KEY": "nasiko-virtual-proxy-key",
    }

def apply_gateway_env_vars() -> None:
    """Flaw 11 fixed: Actually apply the generated gateway environment strings natively."""
    os.environ.update(get_gateway_env_vars())

# [NEW METHOD ONLY] - Priority 4
def inject_mcp_tools(task_object: "Task", mcp_artifact_id: str, manifest: dict) -> "Task":
    """
    Priority 4: Zero-Code Injection.
    Dynamically injects MCP tools into a CrewAI Task at runtime, 
    overriding the agent tools without modifying user source code.
    """
    from .utils.mcp_tools import MCPCrewTool
    import os
    os.environ.update(get_gateway_env_vars())
    
    if not hasattr(task_object, "tools") or task_object.tools is None:
        task_object.tools = []
        
    for tool_def in manifest.get("tools", []):
        props = tool_def.get("input_schema", {}).get("properties", {})
        required = set(tool_def.get("input_schema", {}).get("required", []))
        fields = {
            k: (str, PydanticField(...)) if k in required
            else (str, PydanticField(None))
            for k in props
        }
        DynamicSchema = create_model(f"{tool_def['name']}_schema", **fields)
        
        # Inject the proxy wrapper as a CrewAI BaseTool cleanly aligning Schemas
        proxy_tool = MCPCrewTool(
            name=tool_def.get("name"),
            description=tool_def.get("description", "MCP proxied tool"),
            artifact_id=mcp_artifact_id,
            tool_name_remote=tool_def.get("name"),
            args_schema=DynamicSchema
        )
        
        # Flaw 4 fixed: Bind properly to both the logic Task, and the broader logical Agent context.
        task_object.tools.append(proxy_tool)
        
        if hasattr(task_object, 'agent') and task_object.agent:
            if not hasattr(task_object.agent, 'tools') or task_object.agent.tools is None:
                task_object.agent.tools = []
            task_object.agent.tools.append(proxy_tool)
            
        logger.info(f"Dynamically injected MCP tool '{tool_def.get('name')}' into Task and Agent array.")
        
    return task_object
