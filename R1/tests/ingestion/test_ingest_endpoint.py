"""Tests for the /api/v1/ingest endpoint."""

import io
import zipfile
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.ingest import router


@pytest.fixture
def client():
    """Create a FastAPI test client with the ingest router mounted."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def make_zip(files: dict) -> io.BytesIO:
    """Build an in-memory zip file.

    Args:
        files: Mapping of {"filename.py": "file content string"}.

    Returns:
        A seeked-to-zero BytesIO containing the zip.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    buf.seek(0)
    return buf


def test_valid_mcp_zip_returns_200(client):
    zf = make_zip({"server.py": "from fastmcp import FastMCP"})
    with patch("shutil.rmtree"):
        resp = client.post(
            "/api/v1/ingest",
            files={"file": ("agent.zip", zf, "application/zip")},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["artifact_type"] == "MCP_SERVER"
    for field in [
        "artifact_id",
        "artifact_type",
        "detection_confidence",
        "source_path",
        "entry_point",
        "detected_framework",
        "requirements_path",
        "detected_at",
        "agentcard_exists",
    ]:
        assert field in body


def test_valid_langchain_zip_returns_200(client):
    zf = make_zip({"main.py": "from langchain_core.tools import tool"})
    with patch("shutil.rmtree"):
        resp = client.post(
            "/api/v1/ingest",
            files={"file": ("agent.zip", zf, "application/zip")},
        )
    assert resp.status_code == 200
    assert resp.json()["artifact_type"] == "LANGCHAIN_AGENT"


def test_valid_crewai_zip_returns_200(client):
    zf = make_zip({"main.py": "from crewai import Agent, Task, Crew"})
    with patch("shutil.rmtree"):
        resp = client.post(
            "/api/v1/ingest",
            files={"file": ("agent.zip", zf, "application/zip")},
        )
    assert resp.status_code == 200
    assert resp.json()["artifact_type"] == "CREWAI_AGENT"


def test_ambiguous_two_frameworks_returns_422(client):
    zf = make_zip(
        {"main.py": "from fastmcp import FastMCP\nfrom crewai import Agent"}
    )
    with patch("shutil.rmtree"):
        resp = client.post(
            "/api/v1/ingest",
            files={"file": ("agent.zip", zf, "application/zip")},
        )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "AMBIGUOUS_ARTIFACT"


def test_zero_framework_returns_422(client):
    zf = make_zip({"main.py": "import os, sys"})
    with patch("shutil.rmtree"):
        resp = client.post(
            "/api/v1/ingest",
            files={"file": ("agent.zip", zf, "application/zip")},
        )
    assert resp.status_code == 422
    assert "AMBIGUOUS_ARTIFACT" in resp.json()["detail"]["error"]


def test_non_zip_returns_400(client):
    resp = client.post(
        "/api/v1/ingest",
        files={
            "file": ("agent.tar.gz", io.BytesIO(b"data"), "application/gzip")
        },
    )
    assert resp.status_code == 400


def test_zipslip_returns_400(client):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../etc/passwd", "evil")
    buf.seek(0)
    with patch("shutil.rmtree"):
        resp = client.post(
            "/api/v1/ingest",
            files={"file": ("agent.zip", buf, "application/zip")},
        )
    assert resp.status_code == 400


def test_cleanup_called_on_success(client):
    zf = make_zip({"server.py": "from fastmcp import FastMCP"})
    with patch("app.api.v1.ingest.shutil.rmtree") as mock_rm:
        client.post(
            "/api/v1/ingest",
            files={"file": ("agent.zip", zf, "application/zip")},
        )
        assert mock_rm.called


def test_cleanup_called_on_detection_error(client):
    zf = make_zip({"server.py": "from fastmcp import FastMCP"})
    with patch("app.api.v1.ingest.shutil.rmtree") as mock_rm:
        with patch(
            "app.api.v1.ingest.detect_artifact_type",
            side_effect=Exception("unexpected crash"),
        ):
            try:
                client.post(
                    "/api/v1/ingest",
                    files={"file": ("agent.zip", zf, "application/zip")},
                )
            except Exception:
                pass  # TestClient re-raises unhandled server exceptions
            assert mock_rm.called
