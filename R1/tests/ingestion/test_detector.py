"""
Tests for app.ingestion.detector — 15 tests total.
Uses pytest tmp_path fixture for isolated filesystem operations.
"""
import os
import pytest
from app.ingestion.detector import detect_artifact_type
from app.ingestion.models import ArtifactType, DetectionConfidence
from app.ingestion.exceptions import AmbiguousArtifactError


# ─── Helpers ────────────────────────────────────────────────────

def _write_py(tmp_path, filename: str, content: str):
    """Write a .py file into tmp_path."""
    filepath = tmp_path / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content)


# ─── Framework Detection (tests 1-5) ───────────────────────────

class TestFrameworkDetection:
    """Verify correct framework identification via AST imports."""

    def test_detect_mcp_server_fastmcp(self, tmp_path):
        """MCP detected from 'import fastmcp'."""
        _write_py(tmp_path, "server.py", "import fastmcp\n")
        record = detect_artifact_type(str(tmp_path))
        assert record.artifact_type == ArtifactType.MCP_SERVER
        assert record.detected_framework == "mcp"

    def test_detect_mcp_server_mcp_import(self, tmp_path):
        """MCP detected from 'from mcp.server import Server'."""
        _write_py(tmp_path, "server.py", "from mcp.server import Server\n")
        record = detect_artifact_type(str(tmp_path))
        assert record.artifact_type == ArtifactType.MCP_SERVER
        assert record.detected_framework == "mcp"

    def test_detect_langchain_agent(self, tmp_path):
        """LangChain detected from 'from langchain.agents import ...'."""
        _write_py(tmp_path, "agent.py", "from langchain.agents import AgentExecutor\n")
        record = detect_artifact_type(str(tmp_path))
        assert record.artifact_type == ArtifactType.LANGCHAIN_AGENT
        assert record.detected_framework == "langchain"

    def test_detect_crewai_agent(self, tmp_path):
        """CrewAI detected from 'import crewai'."""
        _write_py(tmp_path, "agent.py", "import crewai\n")
        record = detect_artifact_type(str(tmp_path))
        assert record.artifact_type == ArtifactType.CREWAI_AGENT
        assert record.detected_framework == "crewai"

    def test_detect_mcp_from_submodule_import(self, tmp_path):
        """MCP detected from 'import mcp.server.fastmcp'."""
        _write_py(tmp_path, "main.py", "import mcp.server.fastmcp\n")
        record = detect_artifact_type(str(tmp_path))
        assert record.artifact_type == ArtifactType.MCP_SERVER


# ─── Ambiguous / No Framework (tests 6-7) ──────────────────────

class TestAmbiguousDetection:
    """Verify AmbiguousArtifactError is raised correctly."""

    def test_no_framework_raises_ambiguous(self, tmp_path):
        """No recognized imports → AmbiguousArtifactError."""
        _write_py(tmp_path, "main.py", "import os\nimport sys\n")
        with pytest.raises(AmbiguousArtifactError, match="No recognized framework"):
            detect_artifact_type(str(tmp_path))

    def test_multiple_frameworks_raises_ambiguous(self, tmp_path):
        """Multiple frameworks in same project → AmbiguousArtifactError."""
        _write_py(tmp_path, "a.py", "import fastmcp\n")
        _write_py(tmp_path, "b.py", "import crewai\n")
        with pytest.raises(AmbiguousArtifactError, match="Multiple frameworks"):
            detect_artifact_type(str(tmp_path))


# ─── Entry Point Resolution (tests 8-10) ───────────────────────

class TestEntryPoint:
    """Verify entry point priority: server.py > main.py > agent.py > app.py > fallback."""

    def test_entry_point_server_py(self, tmp_path):
        """server.py takes top priority."""
        _write_py(tmp_path, "server.py", "import fastmcp\n")
        _write_py(tmp_path, "main.py", "# other file\n")
        record = detect_artifact_type(str(tmp_path))
        assert record.entry_point == "server.py"

    def test_entry_point_main_py(self, tmp_path):
        """main.py is used when server.py is absent."""
        _write_py(tmp_path, "main.py", "import fastmcp\n")
        _write_py(tmp_path, "utils.py", "# helper\n")
        record = detect_artifact_type(str(tmp_path))
        assert record.entry_point == "main.py"

    def test_entry_point_fallback(self, tmp_path):
        """Falls back to first .py file when no priority file exists."""
        _write_py(tmp_path, "custom_runner.py", "import crewai\n")
        record = detect_artifact_type(str(tmp_path))
        assert record.entry_point == "custom_runner.py"


# ─── Agentcard Detection (tests 11-12) ─────────────────────────

class TestAgentcard:
    """Verify agentcard.json detection."""

    def test_agentcard_exists(self, tmp_path):
        """agentcard.json found → agentcard_exists=True."""
        _write_py(tmp_path, "server.py", "import fastmcp\n")
        (tmp_path / "agentcard.json").write_text('{"name": "test"}')
        record = detect_artifact_type(str(tmp_path))
        assert record.agentcard_exists is True

    def test_agentcard_not_exists(self, tmp_path):
        """No agentcard.json → agentcard_exists=False."""
        _write_py(tmp_path, "server.py", "import fastmcp\n")
        record = detect_artifact_type(str(tmp_path))
        assert record.agentcard_exists is False


# ─── Requirements Detection (tests 13-14) ──────────────────────

class TestRequirements:
    """Verify requirements.txt detection."""

    def test_requirements_found(self, tmp_path):
        """requirements.txt found → path returned."""
        _write_py(tmp_path, "server.py", "import fastmcp\n")
        (tmp_path / "requirements.txt").write_text("fastmcp>=0.1\n")
        record = detect_artifact_type(str(tmp_path))
        assert record.requirements_path == "requirements.txt"

    def test_requirements_not_found(self, tmp_path):
        """No requirements.txt → None."""
        _write_py(tmp_path, "server.py", "import fastmcp\n")
        record = detect_artifact_type(str(tmp_path))
        assert record.requirements_path is None


# ─── Confidence & Resilience (test 15) ─────────────────────────

class TestConfidenceAndResilience:
    """Verify confidence field and resilience to bad files."""

    def test_confidence_is_high_for_single_framework(self, tmp_path):
        """Single framework → confidence=HIGH."""
        _write_py(tmp_path, "server.py", "import fastmcp\n")
        record = detect_artifact_type(str(tmp_path))
        assert record.confidence == DetectionConfidence.HIGH

    def test_syntax_error_skipped(self, tmp_path):
        """Files with syntax errors are skipped, detection still works."""
        _write_py(tmp_path, "server.py", "import fastmcp\n")
        _write_py(tmp_path, "broken.py", "def foo(\n")  # SyntaxError
        record = detect_artifact_type(str(tmp_path))
        assert record.artifact_type == ArtifactType.MCP_SERVER

    def test_empty_directory_raises_ambiguous(self, tmp_path):
        """Empty directory (no .py files) → AmbiguousArtifactError."""
        with pytest.raises(AmbiguousArtifactError, match="No recognized framework"):
            detect_artifact_type(str(tmp_path))
