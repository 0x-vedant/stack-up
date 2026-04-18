import unittest
import os
from unittest.mock import patch

class TestMCPEndToEnd(unittest.TestCase):
    
    @patch("nasiko.app.agent_builder.get_gateway_env_vars")
    def test_llm_gateway_forces_virtualization(self, mock_env):
        """Validates that agent creation forcefully overwrites the standard API keys."""
        mock_env.return_value = {
            "OPENAI_API_BASE": "http://llm-gateway:4000",
            "OPENAI_API_KEY": "nasiko-virtual-proxy-key"
        }
        
        # Testing integration of environment variables from agent_builder
        from nasiko.app.agent_builder import get_gateway_env_vars, apply_gateway_env_vars
        
        apply_gateway_env_vars()
        self.assertEqual(os.environ.get("OPENAI_API_KEY"), "nasiko-virtual-proxy-key")
        self.assertEqual(os.environ.get("OPENAI_API_BASE"), "http://llm-gateway:4000")
        
        # Cleanup mock
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ.pop("OPENAI_API_BASE", None)

if __name__ == "__main__":
    unittest.main()
