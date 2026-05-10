# AethOS File Write Capability - Complete Fix For Codex

## Problem

The gateway can return `general_chat` instead of recognizing file creation requests when there is no exported parser for file write phrasing in `app/services/host_executor_intent.py`.

## Root Cause

- Regex patterns exist (`_RE_CREATE_FILE_WITH_CONTENT`, `_RE_WRITE`, `_RE_WRITE_CONTENT_TO`).
- A named `parse_file_write_intent` parser was missing for direct intent parsing and tests.
- Gateway file write detection must route through the host executor path before generic chat fallback.

## Fix

### File 1: `app/services/host_executor_intent.py`

Add a parser function that recognizes natural-language file creation requests:

```python
def parse_file_write_intent(text: str) -> dict | None:
    """Parse natural language file write intent."""
    if not text or not isinstance(text, str):
        return None

    text = text.strip()

    match = _RE_WRITE.match(text)
    if match:
        return {
            "filename": match.group(1),
            "content": match.group(2).strip(),
            "directory": None,
        }

    match = _RE_CREATE_FILE_WITH_CONTENT.match(text)
    if match:
        return {
            "filename": match.group(1),
            "content": match.group(2).strip(),
            "directory": match.group(3) if match.lastindex >= 3 and match.group(3) else None,
        }

    match = _RE_WRITE_CONTENT_TO.match(text)
    if match:
        return {
            "filename": match.group(2),
            "content": match.group(1).strip(),
            "directory": None,
        }

    return None
```

### File 2: `app/services/gateway/runtime.py`

Ensure host-executor turns run before sub-agent routing and generic chat fallback. In this codebase the gateway path should call the existing host executor confirmation flow rather than a separate async `handle_file_write_request` helper, because mutating file writes are approval-gated.

Expected routing shape:

```python
host_out = self._try_host_executor_turn(gctx, raw_gate, db_inner)
if host_out is not None:
    return host_out
```

### File 3: `tests/test_file_write_intent.py`

Create tests for:

- `write test.txt with Hello World`
- `Create a file called data.json with content {'test': true}`
- `write 'hello there' to notes.txt`
- `write to notes.txt with hello there`
- non-file prompts
- empty strings
- directory-bearing create prompts

## Verification

Run:

```bash
pytest tests/test_file_write_intent.py -v
pytest tests/test_host_executor_intent.py tests/test_gateway_host_executor_file_write.py tests/test_host_executor_chat.py -q
```

Test via API:

```bash
TOKEN=$(grep NEXA_WEB_API_TOKEN .env | cut -d '=' -f2 | tr -d '"' | xargs)
curl -X POST http://127.0.0.1:8010/api/v1/mission-control/gateway/run \
  -H "X-User-Id: tg_8272800795" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"raw":"write test.txt with Hello World"}'
```

Expected response: not `general_chat`; the turn should route to the host executor file write confirmation/approval flow.

## Expected Outcome

| Before | After |
| --- | --- |
| `{"intent":"general_chat"}` | File write intent detected |
| Generic fallback response | Routes to host executor |
| No file write job queued | File write job can be approved and executed |

## Files To Commit

```bash
git add CODEX_FILE_WRITE_FIX.md
git add app/services/host_executor_intent.py
git add tests/test_file_write_intent.py
git commit -m "feat: add file write intent parser"
git push origin main
```
