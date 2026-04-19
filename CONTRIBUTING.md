# Contributing to Nasiko

## Overview

Nasiko is built in 5 tracks. Each track is a separate component with strict boundary contracts. You will work on **ONE track** at a time, in **ONE focused PR**.

| Track | Component | Package |
|---|---|---|
| R1 | Upload & Detection | `nasiko/app/ingestion/` |
| R2 | Bridge & Kong | `nasiko/mcp_bridge/` |
| R3 | Manifest Generator | `R3/` |
| R4 | Orchestration & Linker | `nasiko/app/agent_builder.py`, `nasiko/app/utils/` |
| R5 | Observability | `nasiko/app/utils/observability/` |

---

## Step 1: Fork & Clone

```bash
# Fork the repo on GitHub first, then:
git clone https://github.com/YOUR-USERNAME/stack-up.git
cd stack-up
git remote add upstream https://github.com/0x-vedant/stack-up.git
git fetch upstream
pip install -e ".[test]"
```

Verify tests pass on clean checkout:
```bash
PYTHONPATH=. pytest tests/ -v
```

**If tests fail on a clean checkout, STOP. Report the failure in a GitHub Issue.**

---

## Step 2: Open a Design Issue BEFORE Writing Code

No PR will be merged without a prior approved Issue.

Go to: `https://github.com/0x-vedant/stack-up/issues/new`

Your Issue **must** include:
- **Track**: R[1-5]
- **Component(s) affected**: exact file paths
- **Problem**: what's missing, broken, or needed
- **Proposed Solution**: which files will be ADDED, MODIFIED, or DELETED
- **Contract Changes**: if any Pydantic model changes, show before/after
- **Files You Will NOT Touch**: components outside your track
- **Estimated Test Count**: how many new tests and what they prove

**Wait for maintainer LGTM before writing code.**

---

## Step 3: Create a Feature Branch

```bash
git checkout main
git pull upstream main
git checkout -b R{track}/short-description
```

Branch name format: `R{track}/short-description` (e.g., `R2/add-shutdown-endpoint`)

Rules:
- ONE branch per Issue
- ONE PR per branch
- Branch from `main`, not from another feature branch

---

## Step 4: Write Code

### Your PR MUST include

| Required | Description |
|---|---|
| Feature code | Minimal diff — only what's needed |
| Tests | Real assertions, not mocks-testing-mocks |
| Docstrings | Every public function and class |
| Type hints | Every function signature |

### Your PR MUST NOT include

| Forbidden | Why |
|---|---|
| Changes to files outside your track | Needs maintainer approval in the Issue first |
| Formatting changes to unrelated code | Creates noise in the diff |
| `eval()`, `exec()`, `shell=True` | AST-enforced constraint |
| Deletion of existing tests | Never remove a passing test |
| Direct file mutations across track boundaries | Use HTTP APIs |
| Committing `__pycache__` or `.pyc` files | These are in `.gitignore` |

### Filesystem Ownership

```
/tmp/nasiko/{artifact_id}/
├── code/            ← R1 WRITES. Everyone else READS.
├── bridge.json      ← R2 WRITES. Others use PATCH /mcp/{id}/status HTTP.
├── manifest.json    ← R3 WRITES. Everyone else READS.
└── orchestration/   ← R4 WRITES. No one else touches.
```

**Violating filesystem ownership will result in PR rejection.**

### Frozen Contract Models (do NOT modify without Issue approval)

- `nasiko/app/ingestion/models.py` → `IngestionRecord`, `ArtifactType`, `DetectionConfidence`
- `nasiko/mcp_bridge/models.py` → `BridgeConfig`
- `R3/generator.py` → `MCPManifest`, `MCPTool`, `MCPResource`, `MCPPrompt`

---

## Step 5: Write Tests

| Track | Test directory |
|---|---|
| R1 | `tests/track1/` |
| R2 | `tests/bridge/` |
| R3 | `tests/track1/` |
| R4 | `tests/orchestration/` or `tests/integration/` |
| R5 | `tests/integration/` |

Test rules:
1. No tautological tests (`assert mock.return_value == mock.return_value` proves nothing)
2. Test behavior, not wiring
3. Use real filesystem fixtures for R1/R3
4. Use `fake_mcp_agent.py` for R2
5. Run the full suite before pushing: `PYTHONPATH=. pytest tests/ -v`

---

## Step 6: Commit & Push

```bash
# Commit message format:
# R{track}: short description
#
# - Detail 1
# - Detail 2
#
# Closes #XX

git push origin R{N}/description
```

---

## Step 7: Open a Pull Request

- **Base**: `0x-vedant/stack-up` → `main`
- **Head**: `YOUR-USERNAME/stack-up` → `R{N}/description`

PR description must include:
- Summary (one paragraph)
- Track (R1-R5)
- Related Issue (`Closes #XX`)
- Files Modified/Added/Deleted with reasons
- Contract Changes (or "None")
- Tests Added with what they prove
- Test Results (paste pytest output)
- Behavior Notes (breaking changes, new env vars, new deps)

---

## Anti-Patterns That Will Get Your PR Rejected

| Anti-Pattern | What to do instead |
|---|---|
| "While I was here" refactoring | Open a separate Issue |
| Cross-track file mutation | Use HTTP APIs |
| Mega PR (15 files, 3 tracks) | One PR per track |
| Tests that only test mocks | Test actual output |
| Breaking a passing test | Fix your code, not the test |
| Adding undeclared dependencies | Add to `pyproject.toml` |
| Hardcoded API keys | Use env vars or LiteLLM gateway |

---

## Quick Reference

```bash
git checkout main && git pull upstream main    # Sync
git checkout -b R{N}/description               # Branch
PYTHONPATH=. pytest tests/ -v                  # Test
git push origin R{N}/description               # Push
```
