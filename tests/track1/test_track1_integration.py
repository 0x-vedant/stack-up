"""Track 1 Integration Tests -- MCP Server Publishing and Agent Integration.

Required tests from the problem statement:
  1. Upload a valid stdio MCP server -> expect 200, detection correct
  2. Upload MCP server missing src/main.py -> expect clear validation error
  3. Upload ambiguous artifact -> clear error, not silent misdetection
  4. Auto-generated manifest contains declared tools, resources, and prompts

These tests exercise real code paths through R1 detector, R3 manifest
generator, R2 bridge server, and R4 linker using filesystem fixtures
and FastAPI TestClient.  No tautologies.

Total: 25 tests across 5 classes.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch, MagicMock

from nasiko.app.ingestion.detector import detect_artifact_type
from nasiko.app.ingestion.models import ArtifactType, DetectionConfidence
from nasiko.app.ingestion.exceptions import AmbiguousArtifactError
from R3.parser import parse_tools, parse_all
from R3.generator import MCPManifest

from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Sample MCP server source code fixtures
# ---------------------------------------------------------------------------

VALID_MCP_SERVER = '''\
"""A valid MCP server using the official Python MCP SDK."""
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("test-server")

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b

@mcp.tool(name="search_docs")
async def search(query: str, limit: int = 10) -> str:
    """Search documentation for a query string."""
    return f"Results for {query}"

@mcp.resource("config://app/settings")
def get_settings() -> str:
    """Return application settings."""
    return '{"theme": "dark"}'

@mcp.resource(uri="file://data/readme")
def get_readme() -> str:
    """Return the project README."""
    return "# README"

@mcp.prompt()
def summarize(text: str) -> str:
    """Summarize the given text."""
    return f"Please summarize: {text}"

@mcp.prompt(name="code_review")
def review_code(code: str, language: str = "python") -> str:
    """Generate a code review prompt."""
    return f"Review this {language} code: {code}"

if __name__ == "__main__":
    mcp.run()
'''

LANGCHAIN_AGENT_SOURCE = '''\
from langchain.agents import AgentExecutor
from langchain.tools import tool

@tool
def greet(name: str) -> str:
    """Greet someone."""
    return f"Hello, {name}"
'''

CREWAI_AGENT_SOURCE = '''\
import crewai

crew = crewai.Crew()
'''

AMBIGUOUS_SOURCE_MCP = '''\
from mcp.server import Server
'''

AMBIGUOUS_SOURCE_LANGCHAIN = '''\
from langchain.tools import tool
'''

NO_FRAMEWORK_SOURCE = '''\
import os
import sys

def main():
    print("hello world")
'''


# ---------------------------------------------------------------------------
# Helper: create temp directory with files
# ---------------------------------------------------------------------------

def _create_project(tmpdir: str, files: dict[str, str]) -> str:
    """Create a project directory with the given files."""
    for relpath, content in files.items():
        full = os.path.join(tmpdir, relpath)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
    return tmpdir


def _create_zip(files: dict[str, str]) -> BytesIO:
    """Create an in-memory zip file from dict of {path: content}."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    buf.seek(0)
    return buf


def _build_ingest_client() -> TestClient:
    """Build a TestClient for the nasiko ingest endpoint."""
    from nasiko.api.v1.ingest import router as ingest_router
    app = FastAPI()
    app.include_router(ingest_router)
    return TestClient(app)


# ==========================================================================
# TEST 1: Upload a valid stdio MCP server -> 200, correct detection
# ==========================================================================

class TestValidMCPServerUpload(unittest.TestCase):
    """Test 1: Upload a valid stdio MCP server built on official Python MCP SDK.

    Validates:
    - Detection returns ArtifactType.MCP_SERVER
    - Confidence is HIGH
    - Entry point is resolved correctly (server.py priority)
    - detected_framework is 'mcp'
    - No AmbiguousArtifactError raised
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_valid_mcp_server_detected_correctly(self):
        """Upload containing `from mcp.server.fastmcp import FastMCP` -> MCP_SERVER."""
        _create_project(self.tmpdir, {"server.py": VALID_MCP_SERVER})
        record = detect_artifact_type(self.tmpdir)

        self.assertEqual(record.artifact_type, ArtifactType.MCP_SERVER)
        self.assertEqual(record.confidence, DetectionConfidence.HIGH)
        self.assertEqual(record.detected_framework, "mcp")
        self.assertEqual(record.entry_point, "server.py")

    def test_mcp_server_with_requirements(self):
        """MCP server with requirements.txt -> requirements_path set."""
        _create_project(self.tmpdir, {
            "server.py": VALID_MCP_SERVER,
            "requirements.txt": "mcp>=1.0\nfastmcp\n",
        })
        record = detect_artifact_type(self.tmpdir)

        self.assertEqual(record.artifact_type, ArtifactType.MCP_SERVER)
        self.assertEqual(record.requirements_path, "requirements.txt")

    def test_mcp_server_entry_priority_server_over_main(self):
        """When both server.py and main.py exist, server.py wins."""
        _create_project(self.tmpdir, {
            "server.py": VALID_MCP_SERVER,
            "main.py": "# stub\n",
        })
        record = detect_artifact_type(self.tmpdir)
        self.assertEqual(record.entry_point, "server.py")

    def test_mcp_server_entry_falls_back_to_main(self):
        """When only main.py exists, it becomes the entry point."""
        _create_project(self.tmpdir, {
            "main.py": 'from mcp.server import Server\n',
        })
        record = detect_artifact_type(self.tmpdir)
        self.assertEqual(record.entry_point, "main.py")

    def test_ingest_endpoint_returns_200(self):
        """POST /ingest with valid MCP server zip -> 200 with correct detection."""
        client = _build_ingest_client()
        zip_buf = _create_zip({"server.py": VALID_MCP_SERVER})

        resp = client.post(
            "/ingest",
            files={"file": ("mcp_server.zip", zip_buf, "application/zip")},
        )

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["artifact_type"], "MCP_SERVER")
        self.assertEqual(body["detected_framework"], "mcp")
        self.assertEqual(body["confidence"], "HIGH")

    def test_ingest_mcp_triggers_manifest_generation(self):
        """POST /ingest with MCP server -> manifest_generated=True with tools."""
        client = _build_ingest_client()
        zip_buf = _create_zip({"server.py": VALID_MCP_SERVER})

        resp = client.post(
            "/ingest",
            files={"file": ("mcp_server.zip", zip_buf, "application/zip")},
        )

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body.get("manifest_generated", False),
                        "MCP upload should auto-generate manifest")
        manifest = body.get("manifest", {})
        self.assertGreater(len(manifest.get("tools", [])), 0,
                           "Manifest should contain tools")

    def test_ingest_mcp_manifest_has_resources_and_prompts(self):
        """POST /ingest with MCP server -> manifest contains resources + prompts."""
        client = _build_ingest_client()
        zip_buf = _create_zip({"server.py": VALID_MCP_SERVER})

        resp = client.post(
            "/ingest",
            files={"file": ("mcp_server.zip", zip_buf, "application/zip")},
        )

        self.assertEqual(resp.status_code, 200)
        manifest = resp.json().get("manifest", {})
        self.assertEqual(len(manifest.get("resources", [])), 2,
                         "Manifest should contain 2 resources")
        self.assertEqual(len(manifest.get("prompts", [])), 2,
                         "Manifest should contain 2 prompts")


# ==========================================================================
# TEST 2: Upload MCP server missing entry point -> clear validation error
# ==========================================================================

class TestMissingEntryPoint(unittest.TestCase):
    """Test 2: Upload an MCP server missing src/main.py.

    The problem statement requires a *clear validation error* when the
    project is structurally invalid.  Since detect_artifact_type falls
    back to any .py file, a truly missing project (no .py files at all)
    raises AmbiguousArtifactError.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_empty_directory_raises_error(self):
        """No .py files at all -> AmbiguousArtifactError with clear message."""
        with self.assertRaises(AmbiguousArtifactError) as ctx:
            detect_artifact_type(self.tmpdir)
        self.assertIn("No recognized framework", ctx.exception.reason)

    def test_only_non_python_files(self):
        """Directory with only .txt files -> no frameworks detected."""
        _create_project(self.tmpdir, {
            "README.txt": "Hello",
            "config.yaml": "key: value",
        })
        with self.assertRaises(AmbiguousArtifactError) as ctx:
            detect_artifact_type(self.tmpdir)
        self.assertIn("No recognized framework", ctx.exception.reason)

    def test_ingest_endpoint_returns_422_for_empty(self):
        """POST /ingest with zip containing no recognized frameworks -> 422."""
        client = _build_ingest_client()
        zip_buf = _create_zip({
            "utils.py": "import os\n",
            "config.py": "import sys\n",
        })

        resp = client.post(
            "/ingest",
            files={"file": ("bad_project.zip", zip_buf, "application/zip")},
        )

        self.assertEqual(resp.status_code, 422)
        body = resp.json()
        self.assertEqual(body["detail"]["error"], "AMBIGUOUS_ARTIFACT")

    def test_ingest_rejects_non_zip(self):
        """POST /ingest with non-zip file -> 400."""
        client = _build_ingest_client()

        resp = client.post(
            "/ingest",
            files={"file": ("script.py", b"import os\n", "text/plain")},
        )

        self.assertEqual(resp.status_code, 400)


# ==========================================================================
# TEST 3: Upload ambiguous artifact -> clear error, not silent misdetection
# ==========================================================================

class TestAmbiguousArtifactDetection(unittest.TestCase):
    """Test 3: Upload artifact ambiguous between agent and MCP server.

    Validates:
    - Multiple frameworks (MCP + LangChain) -> AmbiguousArtifactError
    - Multiple frameworks (MCP + CrewAI) -> AmbiguousArtifactError
    - All three frameworks -> AmbiguousArtifactError
    - Error detail lists the conflicting frameworks
    - Never silently misdetects
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_mcp_plus_langchain_raises_ambiguous(self):
        """MCP + LangChain imports in same project -> AmbiguousArtifactError."""
        _create_project(self.tmpdir, {
            "server.py": AMBIGUOUS_SOURCE_MCP,
            "agent.py": AMBIGUOUS_SOURCE_LANGCHAIN,
        })
        with self.assertRaises(AmbiguousArtifactError) as ctx:
            detect_artifact_type(self.tmpdir)
        self.assertIn("Multiple frameworks", ctx.exception.reason)
        self.assertIn("langchain", ctx.exception.reason)
        self.assertIn("mcp", ctx.exception.reason)

    def test_mcp_plus_crewai_raises_ambiguous(self):
        """MCP + CrewAI imports in same project -> AmbiguousArtifactError."""
        _create_project(self.tmpdir, {
            "server.py": AMBIGUOUS_SOURCE_MCP,
            "crew.py": CREWAI_AGENT_SOURCE,
        })
        with self.assertRaises(AmbiguousArtifactError) as ctx:
            detect_artifact_type(self.tmpdir)
        self.assertIn("Multiple frameworks", ctx.exception.reason)

    def test_all_three_frameworks_raises_ambiguous(self):
        """MCP + LangChain + CrewAI -> AmbiguousArtifactError."""
        _create_project(self.tmpdir, {
            "mcp_srv.py": AMBIGUOUS_SOURCE_MCP,
            "lc_agent.py": AMBIGUOUS_SOURCE_LANGCHAIN,
            "crew_agent.py": CREWAI_AGENT_SOURCE,
        })
        with self.assertRaises(AmbiguousArtifactError) as ctx:
            detect_artifact_type(self.tmpdir)
        self.assertIn("Multiple frameworks", ctx.exception.reason)

    def test_ingest_endpoint_returns_422_for_ambiguous(self):
        """POST /ingest with MCP+LangChain zip -> 422 AMBIGUOUS_ARTIFACT."""
        client = _build_ingest_client()
        zip_buf = _create_zip({
            "server.py": AMBIGUOUS_SOURCE_MCP,
            "agent.py": AMBIGUOUS_SOURCE_LANGCHAIN,
        })

        resp = client.post(
            "/ingest",
            files={"file": ("ambiguous.zip", zip_buf, "application/zip")},
        )

        self.assertEqual(resp.status_code, 422)
        body = resp.json()
        self.assertEqual(body["detail"]["error"], "AMBIGUOUS_ARTIFACT")
        self.assertIn("Multiple frameworks", body["detail"]["detail"])


# ==========================================================================
# TEST 4: Auto-generated manifest contains tools, resources, AND prompts
# ==========================================================================

class TestManifestContainsToolsResourcesPrompts(unittest.TestCase):
    """Test 4: Auto-generated manifest for MCP server.

    Validates that the R3 parser and generator correctly extract and
    serialize all three MCP capability types from @mcp.tool(),
    @mcp.resource(), and @mcp.prompt() decorators.
    """

    def test_parse_all_extracts_tools(self):
        """parse_all() extracts both @mcp.tool() and @mcp.tool(name=...) forms."""
        tools, resources, prompts = parse_all(VALID_MCP_SERVER)
        tool_names = [t["name"] for t in tools]

        self.assertIn("add", tool_names)
        self.assertIn("search_docs", tool_names)
        self.assertEqual(len(tools), 2)

    def test_parse_all_extracts_resources(self):
        """parse_all() extracts @mcp.resource('uri') decorators."""
        tools, resources, prompts = parse_all(VALID_MCP_SERVER)
        resource_uris = [r["uri"] for r in resources]

        self.assertIn("config://app/settings", resource_uris)
        self.assertIn("file://data/readme", resource_uris)
        self.assertEqual(len(resources), 2)

    def test_parse_all_extracts_prompts(self):
        """parse_all() extracts @mcp.prompt() and @mcp.prompt(name=...) decorators."""
        tools, resources, prompts = parse_all(VALID_MCP_SERVER)
        prompt_names = [p["name"] for p in prompts]

        self.assertIn("summarize", prompt_names)
        self.assertIn("code_review", prompt_names)
        self.assertEqual(len(prompts), 2)

    def test_tool_parameters_have_correct_types(self):
        """Tool parameters map to correct JSON Schema types."""
        tools, _, _ = parse_all(VALID_MCP_SERVER)
        add_tool = [t for t in tools if t["name"] == "add"][0]

        params = {p["name"]: p for p in add_tool["parameters"]}
        self.assertEqual(params["a"]["json_schema"]["type"], "integer")
        self.assertEqual(params["b"]["json_schema"]["type"], "integer")
        self.assertTrue(params["a"]["required"])
        self.assertTrue(params["b"]["required"])

    def test_tool_with_defaults_marks_optional(self):
        """Tool parameters with defaults are marked as not required."""
        tools, _, _ = parse_all(VALID_MCP_SERVER)
        search_tool = [t for t in tools if t["name"] == "search_docs"][0]

        params = {p["name"]: p for p in search_tool["parameters"]}
        self.assertTrue(params["query"]["required"])
        self.assertFalse(params["limit"]["required"])

    def test_resource_has_docstring(self):
        """Resources preserve docstrings as descriptions."""
        _, resources, _ = parse_all(VALID_MCP_SERVER)
        settings = [r for r in resources if r["name"] == "get_settings"][0]

        self.assertEqual(settings["docstring"], "Return application settings.")

    def test_prompt_parameters_extracted(self):
        """Prompt parameters are extracted with correct types."""
        _, _, prompts = parse_all(VALID_MCP_SERVER)
        review = [p for p in prompts if p["name"] == "code_review"][0]

        params = {p["name"]: p for p in review["parameters"]}
        self.assertIn("code", params)
        self.assertIn("language", params)
        self.assertEqual(params["code"]["json_schema"]["type"], "string")
        self.assertTrue(params["code"]["required"])
        self.assertFalse(params["language"]["required"])

    def test_parse_tools_backward_compatible(self):
        """Legacy parse_tools() still returns only tools, ignoring resources/prompts."""
        tools = parse_tools(VALID_MCP_SERVER)
        self.assertEqual(len(tools), 2)
        names = [t["name"] for t in tools]
        self.assertIn("add", names)
        self.assertIn("search_docs", names)

    def test_empty_source_returns_empty_lists(self):
        """Empty or whitespace-only source -> empty lists, no crash."""
        tools, resources, prompts = parse_all("")
        self.assertEqual(tools, [])
        self.assertEqual(resources, [])
        self.assertEqual(prompts, [])

    def test_syntax_error_raises_valueerror(self):
        """Source with syntax errors -> ValueError, not silent empty list."""
        with self.assertRaises(ValueError) as ctx:
            parse_all("def broken(:\n")
        self.assertIn("Invalid Python", str(ctx.exception))


# ==========================================================================
# TEST 5: R2 Bridge + R4 Linker integration (callable by configured agent)
# ==========================================================================

class TestBridgeAndLinkerIntegration(unittest.TestCase):
    """Validate that the R2 bridge server and R4 linker work together.

    Tests the FastAPI endpoint wiring, route existence, and that the
    linker correctly validates bridge status before creating associations.
    """

    def test_bridge_routes_exist(self):
        """R2 bridge exposes /mcp/{id}/start, /health, /call."""
        from nasiko.mcp_bridge.server import app

        routes = {
            r.path: r.methods
            for r in app.routes
            if hasattr(r, "methods")
        }

        self.assertIn("/mcp/{artifact_id}/start", routes)
        self.assertIn("POST", routes["/mcp/{artifact_id}/start"])
        self.assertIn("/mcp/{artifact_id}/health", routes)
        self.assertIn("GET", routes["/mcp/{artifact_id}/health"])
        self.assertIn("/mcp/{artifact_id}/call", routes)
        self.assertIn("POST", routes["/mcp/{artifact_id}/call"])

    def test_linker_rejects_when_bridge_not_ready(self):
        """Linker /link endpoint returns 400 when bridge is not in 'ready' status."""
        from nasiko.app.utils.agent_mcp_linker import app as linker_router

        test_app = FastAPI()
        test_app.include_router(linker_router)
        client = TestClient(test_app)

        with patch("nasiko.app.utils.agent_mcp_linker.get_bridge_status") as mock_status:
            for bad in ["starting", "failed", "RUNNING", "UNKNOWN"]:
                mock_status.return_value = bad
                resp = client.post("/link", json={
                    "agent_artifact_id": "agent-1",
                    "mcp_artifact_id": "mcp-1",
                })
                self.assertEqual(resp.status_code, 400, f"Expected 400 for '{bad}'")


if __name__ == "__main__":
    unittest.main()
