"""Interactive native setup wizard — Phase 25 + Phase 32 (boxed steps, welcome screen)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from aethos_cli.env_util import upsert_env_file
from aethos_cli.platform import (
    detect,
    detect_optional_tool,
    human_os_line,
    ollama_install_hint,
)
from aethos_cli.ui import (
    confirm,
    disk_space_line,
    get_input,
    interactive_feature_toggle,
    print_box,
    print_environment_tag,
    print_header,
    print_info,
    print_progress_bar,
    print_step,
    print_success,
    print_warn,
    select,
    validate_anthropic_key,
    validate_deepseek_key,
    validate_openai_key,
)
from aethos_cli.welcome import print_welcome_screen


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _run_cmd(argv: list[str], *, cwd: Path | None = None, timeout: float = 120.0) -> tuple[int, str]:
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, cwd=str(cwd) if cwd else None)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)


def _ollama_status() -> tuple[bool, str, list[str]]:
    exe = shutil.which("ollama")
    if not exe:
        return False, "not installed", []
    code, out = _run_cmd([exe, "list"], timeout=15.0)
    if code != 0:
        return False, f"not responding ({code})", []
    models: list[str] = []
    for line in out.strip().splitlines()[1:]:
        parts = line.split()
        if parts:
            models.append(parts[0].strip())
    return True, "running", models


def _detect_docker() -> bool:
    exe = shutil.which("docker")
    if not exe:
        return False
    code, _ = _run_cmd([exe, "--version"], timeout=8.0)
    return code == 0


def _feat_human(names: list[str]) -> list[str]:
    m = {
        "git": "Git automation & chains",
        "browser": "Browser automation",
        "cron": "Cron scheduling",
        "social": "Social media posting",
        "pr_review": "PR reviews",
        "scraping": "Web scraping",
    }
    return [m.get(x, x) for x in names]


def _configure_primary_llm(
    llm: str,
    *,
    omodels: list[str],
    ok_o: bool,
) -> tuple[dict[str, str], str]:
    """Return env fragment and a short summary label."""
    updates: dict[str, str] = {}
    use_real = "true"
    summary = llm

    if llm == "ollama":
        updates["USE_REAL_LLM"] = use_real
        updates["NEXA_LLM_PROVIDER"] = "ollama"
        updates["NEXA_OLLAMA_ENABLED"] = "true"
        base = get_input("Ollama base URL", "http://127.0.0.1:11434") or "http://127.0.0.1:11434"
        updates["NEXA_OLLAMA_BASE_URL"] = base
        default_model = "llama3"
        if omodels:
            print_info("Detected models: " + ", ".join(omodels[:12]) + ("…" if len(omodels) > 12 else ""))
            default_model = omodels[0]
        model = get_input("Default Ollama model", default_model) or default_model
        updates["NEXA_OLLAMA_DEFAULT_MODEL"] = model
        summary = f"Ollama ({model})"
        if not ok_o:
            print_warn("Ollama not installed — start it later, then run `ollama pull " + model + "`")
    elif llm == "openai":
        while True:
            key = get_input("OpenAI API key", hide=True)
            if not key.strip():
                print_warn("Skipped — add OPENAI_API_KEY in .env later.")
                break
            if validate_openai_key(key.strip()):
                updates["OPENAI_API_KEY"] = key.strip()
                print_success("OpenAI key validated.")
                break
            print_warn("Key did not validate against api.openai.com.")
            if not confirm("Retry?", default=True):
                break
        updates["USE_REAL_LLM"] = use_real
        updates["NEXA_LLM_PROVIDER"] = "openai"
        summary = "OpenAI"
    elif llm == "anthropic":
        key = get_input("Anthropic API key", hide=True)
        if key.strip():
            if validate_anthropic_key(key.strip()):
                updates["ANTHROPIC_API_KEY"] = key.strip()
                print_success("Anthropic key stored (format OK).")
            else:
                print_warn("Key format unexpected — stored anyway.")
                updates["ANTHROPIC_API_KEY"] = key.strip()
        updates["USE_REAL_LLM"] = use_real
        updates["NEXA_LLM_PROVIDER"] = "anthropic"
        summary = "Anthropic (Claude)"
    elif llm == "deepseek":
        key = get_input("DeepSeek API key", hide=True)
        if key.strip():
            if validate_deepseek_key(key.strip()):
                updates["DEEPSEEK_API_KEY"] = key.strip()
            else:
                print_warn("Key looks short — stored anyway.")
                updates["DEEPSEEK_API_KEY"] = key.strip()
        updates["USE_REAL_LLM"] = use_real
        updates["NEXA_LLM_PROVIDER"] = "deepseek"
        summary = "DeepSeek"
    else:
        print_info("Skipping LLM provider — configure later in .env.")
        summary = "configure later"

    return updates, summary


def _optional_extra_provider_keys(updates: dict[str, str], primary: str) -> None:
    """Offer keys for providers not chosen as primary."""
    print_info("Optional: other provider keys (blank skips each).")
    if primary not in ("openai",) and not updates.get("OPENAI_API_KEY"):
        k = get_input("OpenAI API key (optional)", hide=True)
        if k.strip() and validate_openai_key(k.strip()):
            updates["OPENAI_API_KEY"] = k.strip()
            print_success("OpenAI key validated.")
        elif k.strip():
            print_warn("OpenAI key could not be validated — not saved.")
    if primary not in ("anthropic",) and not updates.get("ANTHROPIC_API_KEY"):
        k = get_input("Anthropic API key (optional)", hide=True)
        if k.strip():
            updates["ANTHROPIC_API_KEY"] = k.strip()
            print_success("Anthropic key saved (optional).")
    if primary not in ("deepseek",) and not updates.get("DEEPSEEK_API_KEY"):
        k = get_input("DeepSeek API key (optional)", hide=True)
        if k.strip():
            updates["DEEPSEEK_API_KEY"] = k.strip()


def run_setup_wizard(*, install_kind: str | None = None) -> int:
    """
    Run the setup wizard. ``install_kind`` may be ``fresh`` | ``update`` | ``repair`` from shell.

    When ``NEXA_SETUP_FROM_INSTALLER=1``, steps 1–2 + dependency install were handled by the shell;
    this run covers steps 3–5 (LLM, keys, features) plus saving configuration.
    """
    if install_kind is None:
        install_kind = (os.environ.get("NEXA_SETUP_KIND") or "").strip() or None
    if install_kind and install_kind not in ("fresh", "update", "repair"):
        install_kind = None

    from_installer = os.environ.get("NEXA_SETUP_FROM_INSTALLER") == "1"
    kind: str = install_kind or "fresh"

    root = _repo_root()
    env_path = root / ".env"
    pinfo = detect()
    ok_o, _omsg, omodels = _ollama_status()

    print_header()
    print_environment_tag(human_os_line(pinfo))

    if not from_installer:
        # --- Step 1/6 ---
        print_step("1/6", "Checking prerequisites")
        lines1: list[str] = []
        py_line = f"Python {pinfo.get('python_version', sys.version.split()[0])}"
        lines1.append(f"✓ {py_line}")
        git_v = detect_optional_tool("git")
        if git_v:
            lines1.append(f"✓ Git found ({git_v[:48]}…)" if len(git_v) > 50 else f"✓ Git found ({git_v})")
        else:
            lines1.append("✗ Git not found — install Git to clone/update.")
        node_v = detect_optional_tool("node")
        if node_v:
            lines1.append(f"✓ Node.js optional — {node_v[:56]}")
        else:
            lines1.append("○ Node.js not found (optional, for Next.js / tooling)")
        if ok_o:
            lines1.append(f"✓ Ollama detected ({len(omodels)} model(s) in `ollama list`)")
        else:
            hint = ollama_install_hint()
            lines1.append(f"⚠️ Ollama not installed (optional) — try: {hint}")
        if _detect_docker():
            lines1.append("✓ Docker CLI present")
        print_box("Step 1/6: Prerequisites", lines1)

        # --- Step 2/6 ---
        print_step("2/6", "Installation directory")
        ds_line, ds_ok = disk_space_line(root)
        lines2 = [
            f"Repository: {root}",
            "Typical need: ~500 MB for venv + dependencies.",
            ds_line,
        ]
        if not ds_ok:
            lines2.append("⚠️ Low disk space — free space before large installs.")
        print_box("Step 2/6: Paths & disk", lines2)
        print_info(f"Using Nexa repo at: {root}")
        if get_input("Continue with this directory?", "y").lower() not in ("", "y", "yes"):
            print_warn("Cancelled.")
            return 1

        print_step("2/6", "Installation type")
        kind_options = [
            ("Fresh install — configure .env from scratch", "fresh", "Recommended for new clones"),
            ("Update — merge new keys into existing .env", "update", "Keeps unrelated lines"),
            ("Repair — reinstall deps + rewrite core keys", "repair", "Runs pip install again"),
        ]
        default_kind = 1
        if install_kind in ("fresh", "update", "repair"):
            kind = install_kind
            print_info(f"Installation type: {kind} (from environment)")
        else:
            kind = select("Choose installation type", kind_options, default_index=default_kind)
    else:
        if install_kind in ("fresh", "update", "repair"):
            kind = install_kind
        print_info("Continuing setup (steps 3–6 of 6) — clone and Python deps finished in the installer.")
        time.sleep(0.15)

    # --- Step 3/6 LLM ---
    print_step("3/6", "Select LLM provider")
    prov_opts: list[tuple[str, str, str]] = []
    if ok_o and omodels:
        prov_opts.append(("Ollama (local, private)", "ollama", f"{len(omodels)} model(s) listed ✅"))
    elif ok_o:
        prov_opts.append(("Ollama (local, private)", "ollama", "`ollama list` OK"))
    else:
        prov_opts.append(("Ollama (local, private)", "ollama", "Install Ollama for offline models"))
    prov_opts.extend(
        [
            ("OpenAI (GPT-4 / GPT-4o)", "openai", "Requires API key"),
            ("Anthropic (Claude)", "anthropic", "Requires API key"),
            ("DeepSeek", "deepseek", "Requires API key"),
            ("Skip LLM for now", "skip", "Configure later in .env"),
        ]
    )
    default_idx = 1 if ok_o else 2
    llm = select("LLM provider", prov_opts, default_index=default_idx)

    # --- Step 4/6 keys ---
    print_step("4/6", "Configure API keys")
    updates, llm_summary = _configure_primary_llm(llm, omodels=omodels, ok_o=ok_o)
    _optional_extra_provider_keys(updates, llm)

    # --- Step 5/6 workspace + features ---
    print_step("5/6", "Workspace & features")
    default_ws = str(Path.home() / "nexa-workspace")
    workspace_s = get_input("Workspace directory for projects", default_ws) or default_ws
    ws_path = Path(workspace_s).expanduser().resolve()
    ws_path.mkdir(parents=True, exist_ok=True)
    updates["NEXA_WORKSPACE_ROOT"] = str(ws_path)
    updates["HOST_EXECUTOR_WORK_ROOT"] = str(ws_path)

    feat_opts = [
        ("Git automation & chain actions", "git", "README / commit / push flows"),
        ("Browser automation", "browser", "Playwright browser control"),
        ("Cron scheduling", "cron", "Scheduled tasks"),
        ("Social media posting", "social", "Twitter, LinkedIn, …"),
        ("PR reviews", "pr_review", "Automated GitHub review"),
        ("Web scraping", "scraping", "Extract data from websites"),
    ]
    chosen = interactive_feature_toggle(
        "Select features (type a number to toggle, Enter when done)",
        feat_opts,
        default_enabled=(1, 2, 3),
    )
    updates["NEXA_HOST_EXECUTOR_ENABLED"] = "true" if "git" in chosen else "false"
    updates["NEXA_NL_TO_CHAIN_ENABLED"] = "true" if "git" in chosen else "false"
    updates["NEXA_BROWSER_ENABLED"] = "true" if "browser" in chosen else "false"
    updates["NEXA_CRON_ENABLED"] = "true" if "cron" in chosen else "false"
    updates["NEXA_SOCIAL_ENABLED"] = "true" if "social" in chosen else "false"
    updates["NEXA_PR_REVIEW_ENABLED"] = "true" if "pr_review" in chosen else "false"
    updates["NEXA_SCRAPING_ENABLED"] = "true" if "scraping" in chosen else "false"

    api_base = get_input("API base URL (for CLI + tools)", "http://127.0.0.1:8010") or "http://127.0.0.1:8010"
    updates["API_BASE_URL"] = api_base.rstrip("/")
    updates["NEXA_API_BASE"] = api_base.rstrip("/")

    # --- Save ---
    print_step("6/6", "Saving configuration")
    print_progress_bar("Writing environment", 40)
    if kind == "repair":
        print_info("Repair: reinstalling Python dependencies…")
        print_progress_bar("pip install", 55)
        rc1 = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
            cwd=str(root),
            timeout=180,
        ).returncode
        rc2 = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            cwd=str(root),
            timeout=900,
        ).returncode
        if rc1 != 0 or rc2 != 0:
            print_warn(f"pip returned non-zero ({rc1}, {rc2}) — check output above.")
        print_progress_bar("pip install", 100)

    backup = env_path.with_name(env_path.name + ".bak")
    if env_path.exists():
        try:
            backup.write_text(env_path.read_text(encoding="utf-8"), encoding="utf-8")
            print_success(f"Backed up .env → {backup.name}")
        except OSError as exc:
            print_warn(f"Could not backup .env: {exc}")

    upsert_env_file(env_path, updates)
    print_progress_bar("Writing environment", 100)

    feat_labels = _feat_human(chosen)
    print_welcome_screen(
        install_dir=root,
        workspace=ws_path,
        llm_summary=llm_summary,
        feature_labels=feat_labels,
        api_base=api_base.rstrip("/"),
    )

    try:
        from aethos_cli.cli_status import try_post_install_health_hint

        try_post_install_health_hint()
    except Exception:
        pass

    rc_db = run_database_setup()
    if rc_db != 0:
        print_warn("Database init failed — fix errors above, then run: aethos init-db")

    return 0


def run_database_setup() -> int:
    """
    Run ``ensure_schema()`` in a fresh interpreter so a just-written ``.env`` is picked up
    (avoids stale :func:`~app.core.config.get_settings` cache during interactive ``aethos setup``).
    """
    import os
    import subprocess
    import sys

    root = _repo_root()
    code = "from app.core.db import ensure_schema; ensure_schema()"
    try:
        r = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(root),
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=180,
        )
    except Exception as exc:
        print_warn(f"Could not run database init: {exc}")
        return 1
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()
        print_warn(f"ensure_schema failed: {err[:800]}")
        return r.returncode
    print_success("Database initialized (ensure_schema).")
    return 0


__all__ = ["run_database_setup", "run_setup_wizard"]
