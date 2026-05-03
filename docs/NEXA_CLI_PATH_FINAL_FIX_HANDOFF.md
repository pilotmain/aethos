# NEXA_CLI_PATH_FINAL_FIX_HANDOFF.md

**Title:** Nexa Final CLI PATH Fix (nvm + Full Shell Load)  
**Version:** 1.1 (operator_shell_cli + diagnosis; argv allowlist preserved)  
**Status:** Implemented in-repo — see **§7** for verification  
**Goal:** Load nvm and shell rc files inside a login bash so `vercel` and `gh` resolve like your terminal.

---

## 1. Why Cursor / “you” can run `vercel` but Nexa says it cannot

These are **different processes** with **different environments**:

| Factor | Your interactive terminal | Nexa API / worker process |
|--------|---------------------------|---------------------------|
| **Startup** | Login / interactive shell runs `.zshrc`, `.zprofile`, tools like **nvm** | Often started by **Docker**, **launchd**, **systemd**, or plain `uvicorn` — **no** `.zshrc` unless we explicitly run a shell that sources it |
| **PATH** | Extended by nvm, Homebrew doctor, rbenv, etc. | Often minimal (`/usr/bin:/bin`) unless the supervisor sets `PATH` |
| **HOME** | Your macOS user home | Must match the user that owns `~/.nvm`; in containers **`HOME` may be `/root`** or a path **without** your host’s nvm tree |
| **Filesystem** | Full Mac disk including `~/.nvm/...` | **Containers / remote hosts** may **not** mount your Mac home — `nvm.sh` literally **does not exist** there |

So: **“CLI works on my machine”** in Terminal does **not** imply **the same Python worker** sees those binaries. Nexa only sees what its **process environment + filesystem** provide.

**Non-interactive bash** does not magically load nvm: **nvm is applied by sourcing `nvm.sh`** (or equivalent) after shell startup.

---

## 2. Why we do *not* use a raw `command` string from users

The handoff sketch used `run_with_full_user_shell(command: str, ...)`. In production, passing **unvalidated shell** commands is unsafe.

**Implementation:** `app/services/operator_shell_cli.py` builds:

- **Inner command** with **`shlex.join(argv)`** where **`argv`** is **allowlisted** (`vercel`, `gh`, `git`, `railway`, …).
- **cwd** with **`shlex.quote`**.
- **Outer** runner: **`/bin/bash -lc`** + script that sources **`$NVM_DIR/nvm.sh`**, **`bash_completion`**, then **`~/.zprofile`**, **`~/.zshrc`**, **`~/.bash_profile`**, **`~/.bashrc`**, **`~/.profile`** (failures ignored so zsh-only syntax in `.zshrc` does not abort).

Operator Mode uses this path when **`NEXA_OPERATOR_CLI_PROFILE_SHELL`** is **true** (default). Host executor **`git`** uses the **same** helper when the flag is on.

---

## 3. Related modules (PATH without full shell)

`app/services/operator_cli_path.py` prepends **nvm version bins**, **`~/.local/bin`**, Homebrew, etc., to **`PATH`** when running **direct** `subprocess` (e.g. profile shell **disabled**). This complements but does not replace **sourcing `nvm.sh`** for some installs.

---

## 4. Ultimate shell loader (canonical location)

**Do not duplicate** a second copy only in `host_executor.py`. The canonical script lives in:

- **`run_allowlisted_argv_via_login_shell`** in **`app/services/operator_shell_cli.py`**

`host_executor` only **calls** it for **`git`** when profile shell is enabled.

---

## 5. Clean output

Gateway continues to use existing **precise / zero-nag / `clean_operator_reply_format`** paths from earlier work — no duplicate “minimal output” layer required.

---

## 6. Tests (automated)

- **`tests/test_operator_shell_cli.py`** — asserts **`bash -lc`**, **`nvm.sh`**, and (after v1.1) **`bash_completion`** appear in the script payload (via mocked `subprocess.run`).
- **`tests/test_operator_vercel_runner.py`** — forces profile shell **off** when mocking **`subprocess.run`** so mocks stay stable.
- **`tests/test_local_cli_path.py`** — PATH enrichment when not using profile shell.

Run: `pytest tests/test_operator_shell_cli.py tests/test_operator_vercel_runner.py tests/test_local_cli_path.py -q`

---

## 7. How to verify on the host where Nexa runs

1. **Confirm same machine / same home as your CLI**  
   If Nexa runs **inside Docker** on your Mac, the container must **install** or **mount** nvm/node CLI — **bind-mounting only the repo is not enough**.

2. **Print effective env inside the API process** (one-off):

   ```bash
   curl -s http://127.0.0.1:8000/api/v1/health >/dev/null  # if health exists
   ```

   Or run Python **as the same user/service** that starts uvicorn:

   ```bash
   python -c "import os; print('HOME', os.environ.get('HOME')); print('PATH', os.environ.get('PATH','')[:500])"
   ```

3. **Toggle profile shell**  
   - **`NEXA_OPERATOR_CLI_PROFILE_SHELL=true`** (default): login bash + nvm.sh + rc files.  
   - **`false`**: direct subprocess + enriched PATH only (faster, stricter).

4. **`which vercel`** only matches Nexa if run **inside** the same environment as the worker (same container, same user).

---

## 8. Acceptance criteria (product)

- Operator **`vercel`** / **`gh`** probes use **`operator_shell_cli`** when profile shell is on.
- No arbitrary user-controlled shell strings; **allowlisted argv only**.
- Docs above explain **why** terminal ≠ worker without blaming the user.

---

## 9. Revision history

- **1.0** — Original handoff (string-based runner sketch).
- **1.1** — Document process vs terminal; centralize loader in **`operator_shell_cli`**; add **`bash_completion`** to sourced files; cross-link **`host_executor`** and tests.
