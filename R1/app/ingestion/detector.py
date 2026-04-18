import os
import ast
import uuid
from typing import Set
from .models import IngestionRecord, ArtifactType, DetectionConfidence
from .exceptions import AmbiguousArtifactError


def detect_artifact_type(source_path: str) -> IngestionRecord:
    """
    AST-only detection of artifact type from Python source files.
    NO exec/eval/subprocess — only static analysis.
    """
    # STEP 1: Collect all .py files
    py_files = []
    for root, _, files in os.walk(source_path):
        for file in files:
            if file.endswith('.py'):
                py_files.append(os.path.join(root, file))

    # STEP 2: AST analysis for framework imports
    signals: Set[str] = set()

    for py_file in py_files:
        try:
            with open(py_file, 'r') as f:
                tree = ast.parse(f.read())

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top_level = alias.name.split('.')[0]
                        if top_level in ('fastmcp', 'mcp'):
                            signals.add('mcp')
                        elif top_level == 'langchain':
                            signals.add('langchain')
                        elif top_level == 'crewai':
                            signals.add('crewai')
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        top_level = node.module.split('.')[0]
                        if top_level in ('fastmcp', 'mcp'):
                            signals.add('mcp')
                        elif top_level == 'langchain':
                            signals.add('langchain')
                        elif top_level == 'crewai':
                            signals.add('crewai')

        except SyntaxError:
            # Skip unparseable files
            continue

    # STEP 3: Validate signal count
    if len(signals) == 0:
        raise AmbiguousArtifactError("No recognized framework imports found")
    if len(signals) > 1:
        raise AmbiguousArtifactError(f"Multiple frameworks detected: {sorted(signals)}")

    framework = list(signals)[0]
    artifact_type_map = {
        'mcp': ArtifactType.MCP_SERVER,
        'langchain': ArtifactType.LANGCHAIN_AGENT,
        'crewai': ArtifactType.CREWAI_AGENT
    }

    # STEP 4: Find entry point (priority order)
    priority = ['server.py', 'main.py', 'agent.py', 'app.py']
    entry_point = None
    fallback_entry = None

    for root, _, files in os.walk(source_path):
        for file in sorted(files):
            if file.endswith('.py'):
                rel_path = os.path.relpath(os.path.join(root, file), source_path)
                if file in priority:
                    if entry_point is None or priority.index(file) < priority.index(
                        os.path.basename(entry_point)
                    ):
                        entry_point = rel_path
                elif fallback_entry is None:
                    fallback_entry = rel_path

    if entry_point is None:
        entry_point = fallback_entry

    # STEP 5: Check agentcard.json
    agentcard_exists = any(
        f == 'agentcard.json'
        for _, _, files in os.walk(source_path)
        for f in files
    )

    # STEP 6: Check requirements.txt
    requirements_path = None
    for root, _, files in os.walk(source_path):
        if 'requirements.txt' in files:
            requirements_path = os.path.relpath(
                os.path.join(root, 'requirements.txt'), source_path
            )
            break

    return IngestionRecord(
        artifact_id=str(uuid.uuid4()),
        source_path=source_path,
        artifact_type=artifact_type_map[framework],
        confidence=DetectionConfidence.HIGH,
        entry_point=entry_point,
        detected_framework=framework,
        requirements_path=requirements_path,
        agentcard_exists=agentcard_exists
    )
