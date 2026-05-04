# NEXA_USE_USER_SHELL_AND_NVM_FINAL_HANDOFF.md

**Title:** Nexa Use User's Default Shell + Full nvm Load (Final CLI Fix)  
**Version:** 1.0  
**Status:** Implemented — see `app/services/operator_shell_cli.py`  

## Summary

Operator / profile-shell CLI runs use **`resolve_login_shell_executable()`**:

1. **`$SHELL`** if it exists and is executable (matches Terminal/Cursor when the worker inherits your env).
2. Else **`/bin/zsh`** → **`/bin/bash`** → **`/bin/sh`**.

Invocation: **`[shell, "-l", "-c", script]`** with the same nvm + rc sourcing fragment as before.

**Security:** The inner command is **not** a free-form user string — only **allowlisted argv** joined with **`shlex.join`** (see `run_allowlisted_argv_via_login_shell`).

**Why Cursor “has CLI” but Nexa might not:** The IDE agent runs in **your** terminal session; Nexa runs in **the API worker process** (often Docker/systemd), which may omit **`SHELL`**, **`HOME`**, or the host filesystem — see `docs/NEXA_CLI_PATH_FINAL_FIX_HANDOFF.md`.

## On failure

After a non-zero exit, Nexa appends a short hint from **`command -v`** for the CLI binary, run through the **same** profile script (diagnostic only).
