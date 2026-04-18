"""Integration tests for the MCP E2E pipeline.

These tests use FastAPI TestClient to validate real endpoint behavior.
No tautologies — every assertion depends on server-side logic.
"""

import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from nasiko.app.utils.agent_mcp_linker import app as linker_router
from nasiko.app.agent_builder import (
    get_gateway_env_vars,
    apply_gateway_env_vars,
    inject_mcp_tools,
)


class TestGatewayEnvVars(unittest.TestCase):
    """Verify that env var virtualization actually mutates os.environ."""

    def test_apply_gateway_env_vars_sets_real_env(self):
        """apply_gateway_env_vars must set env WITHOUT mocking get_gateway_env_vars.

        This is not a tautology — it calls the real function and verifies
        that os.environ was actually mutated.
        """
        orig_base = os.environ.get("OPENAI_API_BASE")
        orig_key = os.environ.get("OPENAI_API_KEY")

        try:
            apply_gateway_env_vars()

            expected = get_gateway_env_vars()
            self.assertEqual(os.environ["OPENAI_API_BASE"], expected["OPENAI_API_BASE"])
            self.assertEqual(os.environ["OPENAI_API_KEY"], expected["OPENAI_API_KEY"])
            self.assertEqual(os.environ["OPENAI_BASE_URL"], expected["OPENAI_BASE_URL"])
            self.assertEqual(os.environ["ANTHROPIC_API_KEY"], expected["ANTHROPIC_API_KEY"])
        finally:
            for key in ["OPENAI_API_BASE", "OPENAI_API_KEY", "OPENAI_BASE_URL", "ANTHROPIC_API_KEY"]:
                if key == "OPENAI_API_BASE" and orig_base is not None:
                    os.environ[key] = orig_base
                elif key == "OPENAI_API_KEY" and orig_key is not None:
                    os.environ[key] = orig_key
                else:
                    os.environ.pop(key, None)


class TestLinkerEndpointIntegration(unittest.TestCase):
    """Test /link endpoint through a real FastAPI TestClient."""

    @classmethod
    def setUpClass(cls):
        cls.app = FastAPI()
        cls.app.include_router(linker_router)
        cls.client = TestClient(cls.app)

    @patch("nasiko.app.utils.agent_mcp_linker.get_manifest")
    @patch("nasiko.app.utils.agent_mcp_linker.get_bridge_status")
    def test_link_succeeds_when_bridge_ready(self, mock_status, mock_manifest):
        mock_status.return_value = "ready"
        mock_manifest.return_value = {"tools": [
            {"name": "search"},
            {"name": "calculate"},
        ]}
        resp = self.client.post("/link", json={
            "agent_artifact_id": "agent-a",
            "mcp_artifact_id": "mcp-b",
        })
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["linked_mcp"], "mcp-b")
        self.assertIn("search", body["available_tools"])
        self.assertIn("calculate", body["available_tools"])

    @patch("nasiko.app.utils.agent_mcp_linker.get_bridge_status")
    def test_link_rejects_non_ready_status(self, mock_status):
        for bad_status in ["starting", "failed", "RUNNING", "UNKNOWN"]:
            mock_status.return_value = bad_status
            resp = self.client.post("/link", json={
                "agent_artifact_id": "a",
                "mcp_artifact_id": "b",
            })
            self.assertEqual(
                resp.status_code, 400,
                f"Expected 400 for status '{bad_status}', got {resp.status_code}"
            )


class TestToolInjectionTypes(unittest.TestCase):
    """Verify that inject_mcp_tools respects input_schema types."""

    def test_type_mapping_applied(self):
        class MockTask:
            tools = []

        task = MockTask()
        manifest = {
            "tools": [{
                "name": "calculate",
                "description": "Does math",
                "input_schema": {
                    "properties": {
                        "x": {"type": "integer"},
                        "y": {"type": "number"},
                        "verbose": {"type": "boolean"},
                        "label": {"type": "string"},
                    },
                    "required": ["x", "y"],
                },
            }]
        }

        inject_mcp_tools(task, "mcp-calc", manifest)
        self.assertEqual(len(task.tools), 1)
        tool = task.tools[0]
        schema = tool.args_schema

        fields = schema.model_fields
        self.assertEqual(fields["x"].annotation, int)
        self.assertEqual(fields["y"].annotation, float)
        self.assertEqual(fields["verbose"].annotation, bool)
        self.assertEqual(fields["label"].annotation, str)


if __name__ == "__main__":
    unittest.main()
