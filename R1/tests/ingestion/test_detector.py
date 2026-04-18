"""Tests for the artifact detection logic."""

import pytest

from app.ingestion.detector import detect_artifact_type
from app.ingestion.models import ArtifactType, DetectionConfidence
from app.ingestion.exceptions import AmbiguousArtifactError


def test_detects_mcp_from_fastmcp_import(tmp_path):
    (tmp_path / "server.py").write_text("from fastmcp import FastMCP")
    result = detect_artifact_type(str(tmp_path))
    assert result.artifact_type == ArtifactType.MCP_SERVER
    assert result.detected_framework == "fastmcp"


def test_detects_mcp_from_mcp_server_import(tmp_path):
    (tmp_path / "server.py").write_text(
        "from mcp.server.fastmcp import FastMCP"
    )
    result = detect_artifact_type(str(tmp_path))
    assert result.artifact_type == ArtifactType.MCP_SERVER


def test_detects_langchain_agent(tmp_path):
    (tmp_path / "main.py").write_text(
        "from langchain_core.tools import tool"
    )
    result = detect_artifact_type(str(tmp_path))
    assert result.artifact_type == ArtifactType.LANGCHAIN_AGENT
    assert result.detected_framework == "langchain"


def test_detects_crewai_agent(tmp_path):
    (tmp_path / "main.py").write_text(
        "from crewai import Agent, Task, Crew"
    )
    result = detect_artifact_type(str(tmp_path))
    assert result.artifact_type == ArtifactType.CREWAI_AGENT
    assert result.detected_framework == "crewai"


def test_raises_on_zero_frameworks(tmp_path):
    (tmp_path / "main.py").write_text("import os\nimport sys")
    with pytest.raises(AmbiguousArtifactError):
        detect_artifact_type(str(tmp_path))


def test_raises_on_multiple_frameworks(tmp_path):
    (tmp_path / "main.py").write_text(
        "from fastmcp import FastMCP\nfrom crewai import Agent"
    )
    with pytest.raises(AmbiguousArtifactError) as exc_info:
        detect_artifact_type(str(tmp_path))
    assert "Multiple frameworks" in str(exc_info.value)


def test_agentcard_exists_true(tmp_path):
    (tmp_path / "main.py").write_text("from crewai import Agent")
    (tmp_path / "agentcard.json").write_text('{"name": "test"}')
    result = detect_artifact_type(str(tmp_path))
    assert result.agentcard_exists is True


def test_agentcard_exists_false(tmp_path):
    (tmp_path / "main.py").write_text("from crewai import Agent")
    result = detect_artifact_type(str(tmp_path))
    assert result.agentcard_exists is False


def test_entry_point_priority_server_py(tmp_path):
    (tmp_path / "server.py").write_text("from fastmcp import FastMCP")
    (tmp_path / "main.py").write_text("from fastmcp import FastMCP")
    result = detect_artifact_type(str(tmp_path))
    assert result.entry_point == "server.py"


def test_entry_point_priority_main_over_agent(tmp_path):
    (tmp_path / "main.py").write_text("from crewai import Agent")
    (tmp_path / "agent.py").write_text("from crewai import Task")
    result = detect_artifact_type(str(tmp_path))
    assert result.entry_point == "main.py"


def test_requirements_path_present(tmp_path):
    (tmp_path / "main.py").write_text("from fastmcp import FastMCP")
    (tmp_path / "requirements.txt").write_text("fastmcp==0.1.0")
    result = detect_artifact_type(str(tmp_path))
    assert result.requirements_path is not None
    assert "requirements.txt" in result.requirements_path


def test_requirements_path_absent(tmp_path):
    (tmp_path / "main.py").write_text("from fastmcp import FastMCP")
    result = detect_artifact_type(str(tmp_path))
    assert result.requirements_path is None


def test_all_contract_fields_present(tmp_path):
    (tmp_path / "server.py").write_text("from fastmcp import FastMCP")
    result = detect_artifact_type(str(tmp_path))
    d = result.model_dump()
    required = [
        "artifact_id",
        "artifact_type",
        "detection_confidence",
        "source_path",
        "entry_point",
        "detected_framework",
        "requirements_path",
        "detected_at",
        "agentcard_exists",
    ]
    for field in required:
        assert field in d, f"Missing field: {field}"


def test_artifact_id_unique_per_call(tmp_path):
    (tmp_path / "server.py").write_text("from fastmcp import FastMCP")
    r1 = detect_artifact_type(str(tmp_path))
    r2 = detect_artifact_type(str(tmp_path))
    assert r1.artifact_id != r2.artifact_id


def test_detection_confidence_high(tmp_path):
    (tmp_path / "server.py").write_text("from fastmcp import FastMCP")
    result = detect_artifact_type(str(tmp_path))
    assert result.detection_confidence == DetectionConfidence.HIGH


def test_skips_unparseable_py_file(tmp_path):
    (tmp_path / "broken.py").write_text("def (((broken syntax")
    (tmp_path / "server.py").write_text("from fastmcp import FastMCP")
    result = detect_artifact_type(str(tmp_path))
    assert result.artifact_type == ArtifactType.MCP_SERVER
