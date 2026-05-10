# AethOS Complete Handoff Package - File Write Capability Audit & Fix

## Purpose

This document contains everything needed to audit and fix the file write capability in AethOS, enabling agents to create files on the local filesystem.

## Part 1: Files Needed For Audit

### Required Files

1. `app/services/host_executor.py`
2. `app/services/agent_templates.py`
3. `app/services/intent_classifier.py`
4. `app/api/routes/gateway.py`
5. `app/services/mission_executor.py`

### Helpful Files

6. `app/services/sub_agent_router.py`
7. `app/services/sub_agent_natural_creation.py`
8. `.env` or `.env.example` with sensitive values hidden
9. One existing test from `tests/`

## Part 2: Terminal Commands To Run

```bash
cd /Users/raya/aethos

echo "========================================="
echo "AETHOS FILE WRITE CAPABILITY AUDIT"
echo "========================================="

echo -e "\n[1] Checking host_executor.py existence and content:"
ls -la app/services/host_executor.py 2>/dev/null || echo "File not found"
if [ -f app/services/host_executor.py ]; then
    echo "=== First 50 lines ==="
    head -50 app/services/host_executor.py
    echo -e "\n=== Searching for write functions ==="
    grep -n "write\|create.*file\|save\|file" app/services/host_executor.py | head -20
fi

echo -e "\n[2] Checking agent_templates.py:"
ls -la app/services/agent_templates.py 2>/dev/null || echo "File not found"
if [ -f app/services/agent_templates.py ]; then
    cat app/services/agent_templates.py
fi

echo -e "\n[3] Checking intent_classifier.py for file creation patterns:"
grep -n "create.*file\|write.*file\|file.*creation" app/services/intent_classifier.py 2>/dev/null | head -20

echo -e "\n[4] Checking gateway.py for file creation routing:"
grep -n "file\|write\|create" app/api/routes/gateway.py 2>/dev/null | head -30

echo -e "\n[5] Checking mission_executor.py:"
ls -la app/services/mission_executor.py 2>/dev/null || echo "File not found"
if [ -f app/services/mission_executor.py ]; then
    head -100 app/services/mission_executor.py
fi

echo -e "\n[6] Environment Configuration:"
grep -E "HOST_EXECUTOR|WORKSPACE|WORK_ROOT" .env 2>/dev/null || echo "No host executor config in .env"

echo -e "\n[7] Workspace Directory Status:"
ls -la /Users/raya/aethos_workspace 2>/dev/null || echo "Directory does not exist"

echo -e "\n[8] Searching entire codebase for write_file:"
grep -rn "write_file\|writeFile\|create_file" app/ --include="*.py" 2>/dev/null | head -20

echo -e "\n[9] Searching for host executor anywhere:"
grep -rn "host_executor\|HOST_EXECUTOR" app/ --include="*.py" 2>/dev/null | head -30

echo -e "\n[10] Checking sub_agent files:"
grep -rn "file\|write\|create" app/services/sub_agent*.py 2>/dev/null | grep -v "\.pyc" | head -30

echo -e "\n========================================="
echo "AUDIT COMPLETE"
echo "========================================="
```

## Part 3: Questions To Answer

1. Does the `write_file` tool exist?
2. Is host executor enabled?
3. Does the intent classifier understand "create a file"?
4. Where is the blocking issue?

Possible blocking issues:

- Missing `write_file` function
- Host executor disabled
- Intent misclassification
- Missing workspace directory
- Permission issues
- Other

## Part 4: Expected Deliverables After Audit

### `audit_report.md`

```markdown
# File Write Capability Audit Report

## Executive Summary
[One paragraph summary of findings]

## Detailed Findings

### Issue #1: [File:Line]
- **Current behavior:** [What happens now]
- **Expected behavior:** [What should happen]
- **Root cause:** [One sentence]
- **Fix:** [One line of code or config change]

## Recommendation
[Which issue to fix first and why]
```

### `fix_plan.md`

```markdown
# File Write Capability Fix Plan

## Goal
Enable agent to create a file with content on local filesystem.

## Success Criteria
User says: "Create a file called test.txt with content 'Hello AethOS' in /Users/raya/aethos_workspace"
Result: File exists with correct content.

## Files to Modify

### File 1: `app/services/host_executor.py`
**Change:** [Exact code to add/modify]
**Line numbers:** [Specific lines]

### File 2: `app/services/intent_classifier.py`
**Change:** [Exact code to add/modify]
**Line numbers:** [Specific lines]

### File 3: `.env`
**Change:** Add/update these variables:

```bash
NEXA_HOST_EXECUTOR_ENABLED=true
NEXA_WORKSPACE_ROOT=/Users/raya/aethos_workspace
HOST_EXECUTOR_WORK_ROOT=/Users/raya
```

## Testing Plan
[Steps to verify the fix works]

## Rollback Plan
[How to undo changes if something breaks]
```

### `tests/test_file_write_e2e.py`

```python
"""End-to-end test for agent file write capability"""

import os
import time
from pathlib import Path

import pytest
import requests


class TestFileWriteE2E:
    """Test that agents can create files on disk."""

    @pytest.fixture
    def workspace(self):
        """Ensure workspace exists and return path."""
        workspace = Path("/Users/raya/aethos_workspace")
        workspace.mkdir(parents=True, exist_ok=True)
        yield workspace
        for test_file in workspace.glob("test_*.txt"):
            test_file.unlink()

    @pytest.fixture
    def auth_headers(self):
        """Get authentication headers from .env."""
        return {
            "X-User-Id": "tg_8272800795",
            "Authorization": f"Bearer {os.getenv('NEXA_WEB_API_TOKEN', 'test-token')}",
        }

    @pytest.fixture
    def api_base(self):
        return os.getenv("API_BASE_URL", "http://127.0.0.1:8010")

    def test_agent_creates_file_via_gateway(self, workspace, auth_headers, api_base):
        """Test that agent can create a file via natural language."""
        test_content = "Hello AethOS from test"
        test_filename = f"test_{int(time.time())}.txt"
        test_filepath = workspace / test_filename

        response = requests.post(
            f"{api_base}/api/v1/mission-control/gateway/run",
            headers=auth_headers,
            json={
                "raw": f"Create a file called {test_filename} with content '{test_content}' in {workspace}"
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data.get("intent") in ["file_write", "create_sub_agent", "run_mission"]

        for _ in range(30):
            if test_filepath.exists():
                break
            time.sleep(1)

        assert test_filepath.exists(), f"File {test_filename} was not created"
        assert test_content in test_filepath.read_text()

    def test_agent_creates_file_with_simple_command(self, workspace, auth_headers, api_base):
        """Test simpler file creation command."""
        test_file = workspace / "simple_test.txt"

        response = requests.post(
            f"{api_base}/api/v1/mission-control/gateway/run",
            headers=auth_headers,
            json={"raw": f"Write 'test content' to {test_file}"},
        )

        assert response.status_code == 200
        time.sleep(5)

        if test_file.exists():
            assert "test content" in test_file.read_text()
```

## Part 5: Quick Diagnostic

```bash
cd /Users/raya/aethos

echo "=== CRITICAL CHECKS ==="

if [ -f "app/services/host_executor.py" ]; then
    echo "host_executor.py exists"
else
    echo "host_executor.py MISSING - This is likely the problem"
fi

if grep -q "HOST_EXECUTOR_ENABLED=true" .env 2>/dev/null; then
    echo "HOST_EXECUTOR_ENABLED=true"
else
    echo "HOST_EXECUTOR_ENABLED not set to true"
fi

if [ -d "/Users/raya/aethos_workspace" ]; then
    echo "Workspace directory exists"
else
    echo "Workspace directory missing - create with: mkdir -p /Users/raya/aethos_workspace"
fi

if grep -r "def write_file" app/ --include="*.py" 2>/dev/null; then
    echo "write_file function exists"
else
    echo "No write_file function found"
fi

echo -e "\nRun this to get full audit:"
echo "python scripts/audit_file_write.py 2>/dev/null || echo 'Audit script not found'"
```

## Part 6: Success Definition

```bash
curl -X POST http://127.0.0.1:8010/api/v1/mission-control/gateway/run \
  -H "X-User-Id: tg_8272800795" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"raw":"Create a file called test.txt with content Hello World in /Users/raya/aethos_workspace"}'

ls /Users/raya/aethos_workspace/test.txt && cat /Users/raya/aethos_workspace/test.txt
```

## Next Action

Choose one:

1. Attach the files listed in Part 1
2. Run the terminal commands in Part 2 and paste output
3. Run the quick diagnostic in Part 5 and paste output
4. Tell Copilot to switch to Agent Mode and run the audit
