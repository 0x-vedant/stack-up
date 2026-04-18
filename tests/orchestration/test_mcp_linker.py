import pytest
from unittest.mock import patch, MagicMock

# Import the R4 methods we just injected
from nasiko.app.utils.agent_mcp_linker import get_bridge_status
from nasiko.app.agent_builder import inject_mcp_tools

class MockTask:
    def __init__(self):
        self.tools = []

@patch("nasiko.app.utils.agent_mcp_linker.Path.exists")
@patch("nasiko.app.utils.agent_mcp_linker.open")
def test_agent_mcp_linker_status(mock_open, mock_exists):
    """Priority 3 verification: Mock filesystem reads for bridge status."""
    mock_exists.return_value = True
    # Fake the bridge.json output matching a live process
    mock_open.return_value.__enter__.return_value.read.return_value = '{"status": "RUNNING"}'
    
    assert get_bridge_status("mock-mcp-123") == "RUNNING"

def test_inject_mcp_tools_zero_code_guarantee():
    """
    Priority 4 verification: Test that tools array is dynamically 
    appended, bypassing need for source code modification.
    """
    task = MockTask()
    manifest = {
        "tools": [
            {"name": "fetch_market_data", "description": "Fetches market info"}
        ]
    }
    
    inject_mcp_tools(task, "mock-mcp-123", manifest)
    
    assert len(task.tools) == 1
    injected_tool = task.tools[0]
    
    # Needs to match the proxy schema
    assert injected_tool.name == "fetch_market_data"
    assert injected_tool.artifact_id == "mock-mcp-123"
