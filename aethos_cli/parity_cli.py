# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""OpenClaw-class CLI helpers: ``doctor`` (sanity) and ``logs`` (local tail)."""

from __future__ import annotations

import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _tail_file(path: Path, *, max_lines: int) -> list[str]:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    if len(raw) <= max_lines:
        return raw
    return raw[-max_lines:]


def _home_log_roots() -> list[Path]:
    from app.core.paths import get_aethos_home_dir

    h = get_aethos_home_dir() / "logs"
    h.mkdir(parents=True, exist_ok=True)
    roots = [h]
    rt = _repo_root() / ".runtime"
    if rt.is_dir():
        roots.append(rt)
    return roots


def _log_name_matches_category(name: str, category: str | None) -> bool:
    n = name.lower()
    if not category:
        return True
    if category == "gateway":
        return any(x in n for x in ("gateway", "uvicorn", "aethos", "api"))
    if category == "agents":
        return "agent" in n
    if category == "deployments":
        return "deploy" in n
    if category == "runtime":
        return any(x in n for x in ("runtime", "heartbeat", "recovery"))
    if category == "orchestration":
        return "orchestration" in n
    if category == "recovery":
        return "recovery" in n
    if category == "execution":
        return n == "execution.log" or ("execution" in n and "orchestration" not in n)
    if category == "checkpoints":
        return "checkpoint" in n
    if category == "retries":
        return "retries" in n
    if category == "scheduler":
        return n == "scheduler.log"
    if category == "planning":
        return n == "planning.log"
    if category == "reasoning":
        return n == "reasoning.log"
    if category == "optimization":
        return n == "optimization.log"
    if category == "replanning":
        return n == "replanning.log"
    if category == "adaptive_execution":
        return n == "adaptive_execution.log"
    if category == "delegation_optimization":
        return n == "delegation_optimization.log"
    if category == "runtime_backups":
        return n == "runtime_backups.log"
    if category == "runtime_corruption":
        return n == "runtime_corruption.log"
    if category == "queue_repair":
        return n == "queue_repair.log"
    if category == "cleanup":
        return n == "cleanup.log"
    if category == "runtime_recovery":
        return n == "runtime_recovery.log"
    if category == "runtime_integrity":
        return n == "runtime_integrity.log"
    return True


def cmd_logs(*, lines: int = 80, category: str | None = None) -> int:
    """Print recent lines from ``~/.aethos/logs/*.log`` or ``<repo>/.runtime/*.log``."""
    if category == "runtime":
        from app.core.paths import get_runtime_state_path

        p = get_runtime_state_path()
        if p.is_file():
            print(f"--- {p} (last {lines} lines) ---", file=sys.stderr)
            for ln in _tail_file(p, max_lines=max(1, int(lines))):
                print(ln)
            return 0
        print("No ~/.aethos/aethos.json yet — start ``aethos gateway`` once.", file=sys.stderr)
        return 0
    if category in (
        "orchestration",
        "recovery",
        "deployments",
        "deployment_health",
        "deployment_recovery",
        "environments",
        "rollback",
        "operations",
        "agents",
        "agent_supervisor",
        "agent_delegation",
        "autonomous_loops",
        "runtime_supervision",
        "gateway",
        "execution",
        "checkpoints",
        "retries",
        "scheduler",
        "tools",
        "workflows",
        "runtime_events",
        "runtime_sessions",
        "runtime_metrics",
        "planning",
        "reasoning",
        "optimization",
        "replanning",
        "adaptive_execution",
        "delegation_optimization",
        "runtime_backups",
        "runtime_corruption",
        "queue_repair",
        "cleanup",
        "runtime_recovery",
        "runtime_integrity",
    ):
        from app.core.paths import get_aethos_home_dir

        p = get_aethos_home_dir() / "logs" / f"{category}.log"
        if p.is_file():
            print(f"--- {p} (last {lines} lines) ---", file=sys.stderr)
            for ln in _tail_file(p, max_lines=max(1, int(lines))):
                print(ln)
            return 0
        print(f"No {p.name} yet — run the API with orchestration once.", file=sys.stderr)
        return 0

    candidates: list[Path] = []
    for d in _home_log_roots():
        if not d.is_dir():
            continue
        for p in d.glob("*.log"):
            if p.is_file() and _log_name_matches_category(p.name, category):
                candidates.append(p)
    if not candidates:
        print(
            "No matching ``*.log`` files.\n"
            "Try: ``aethos logs`` (all) or ``aethos logs gateway|…|runtime_events|runtime_sessions|runtime_metrics``.",
            file=sys.stderr,
        )
        return 0

    newest = max(candidates, key=lambda p: p.stat().st_mtime)
    print(f"--- {newest} (last {lines} lines) ---", file=sys.stderr)
    for ln in _tail_file(newest, max_lines=max(1, int(lines))):
        print(ln)
    return 0


def _runtime_doctor_messages() -> list[str]:
    out: list[str] = []
    try:
        from app.runtime.runtime_workspace import ensure_runtime_workspace_layout

        ensure_runtime_workspace_layout()
        out.append("runtime_workspace: OK")
    except Exception as exc:
        out.append(f"runtime_workspace: FAIL ({exc})")
        return out
    try:
        from app.core.paths import get_runtime_state_path, get_aethos_workspace_root
        from app.runtime.runtime_recovery import reconcile_stale_gateway_pid
        from app.runtime.runtime_state import load_runtime_state, save_runtime_state

        ws = get_aethos_workspace_root()
        out.append(f"workspace_root exists={ws.is_dir()} path={ws}")
        p = get_runtime_state_path()
        if not p.is_file():
            out.append("aethos.json: absent (created on next API boot)")
            return out
        st = load_runtime_state()
        reconcile_stale_gateway_pid(st)
        from app.orchestration.task_queue import QUEUE_NAMES, prune_orphan_queue_entries
        from app.orchestration.task_registry import TASK_STATES

        bad_q = 0
        for qn in QUEUE_NAMES:
            q = st.get(qn)
            if not isinstance(q, list):
                bad_q += 1
        if bad_q:
            out.append(f"orchestration_queues: FAIL ({bad_q} non-list queue(s))")
        else:
            out.append("orchestration_queues: OK (list shapes)")
        pruned = prune_orphan_queue_entries(st)
        if pruned:
            out.append(f"orchestration_queues: pruned {pruned} orphan queue ref(s)")
        tr = st.get("task_registry")
        if not isinstance(tr, dict):
            out.append("task_registry: FAIL (not an object)")
        else:
            bad_states = 0
            for t in tr.values():
                if isinstance(t, dict) and str(t.get("state") or "") not in TASK_STATES:
                    bad_states += 1
            if bad_states:
                out.append(f"task_registry: FAIL ({bad_states} invalid state(s))")
            else:
                out.append("task_registry: OK")
        orch = st.get("orchestration")
        if not isinstance(orch, dict) or not isinstance(orch.get("checkpoints"), dict):
            out.append("orchestration_checkpoints: FAIL")
        else:
            out.append("orchestration_checkpoints: OK")
        sch = orch.get("scheduler") if isinstance(orch, dict) else None
        if not isinstance(sch, dict):
            out.append("scheduler_state: FAIL")
        else:
            out.append("scheduler_state: OK")
        deps = st.get("deployments")
        if deps is not None and not isinstance(deps, list):
            out.append("deployments: FAIL (not a list)")
        else:
            out.append("deployments: OK")
        from app.execution import execution_dependencies
        from app.execution import execution_plan

        ex = st.get("execution")
        if not isinstance(ex, dict):
            out.append("execution: FAIL (not an object)")
        else:
            bad_plans = 0
            for plan in (ex.get("plans") or {}).values():
                if not isinstance(plan, dict):
                    bad_plans += 1
                    continue
                if not execution_dependencies.validate_plan_dependency_dag(plan):
                    bad_plans += 1
            if bad_plans:
                out.append(f"execution_graphs: FAIL ({bad_plans} invalid DAG(s))")
            else:
                out.append("execution_graphs: OK")
            cpx = ex.get("checkpoints")
            if cpx is not None and not isinstance(cpx, dict):
                out.append("execution_checkpoints: FAIL")
            else:
                out.append("execution_checkpoints: OK")
            bad_retry = 0
            for plan in (ex.get("plans") or {}).values():
                if not isinstance(plan, dict):
                    continue
                for s in plan.get("steps") or []:
                    if (
                        isinstance(s, dict)
                        and str(s.get("status")) == "retrying"
                        and int(s.get("retry_count") or 0) > 0
                        and s.get("next_retry_at") is None
                    ):
                        bad_retry += 1
            if bad_retry:
                out.append(f"execution_retry_integrity: FAIL ({bad_retry} step(s))")
            else:
                out.append("execution_retry_integrity: OK")
            from app.execution import workflow_recovery

            wrep = workflow_recovery.workflow_integrity_report(st)
            if wrep.get("ok"):
                out.append("workflow_plan_integrity: OK")
            else:
                out.append(f"workflow_plan_integrity: FAIL {wrep.get('issues')}")
            try:
                probe = ws / ".aethos_write_probe"
                probe.write_text("ok", encoding="utf-8")
                probe.unlink(missing_ok=True)
                out.append("workspace_writable: OK")
            except OSError as exc:
                out.append(f"workspace_writable: FAIL ({exc})")
            from app.services.host_executor import is_command_safe

            out.append("shell_allowlist_echo: " + ("OK" if is_command_safe("echo parity_doctor") else "FAIL"))
            from app.runtime.integrity.runtime_integrity import validate_runtime_state

            inv = validate_runtime_state(st)
            if inv.get("ok"):
                out.append("runtime_integrity: OK")
            else:
                out.append(f"runtime_integrity: FAIL ({inv.get('issue_count', 0)} issue(s))")
                for i in (inv.get("issues") or [])[:15]:
                    out.append(f"  - {i}")
            try:
                from app.runtime import runtime_reliability

                rel = runtime_reliability.summarize_runtime_reliability(st)
                out.append(
                    f"runtime_reliability: {rel.get('severity')} "
                    f"(integrity_ok={rel.get('integrity_ok')} issues={rel.get('integrity_issue_count')})"
                )
                rs = rel.get("stability_counters") or {}
                out.append(
                    f"  stability: restarts={int(rs.get('restart_cycles') or 0)} "
                    f"recoveries={int(rs.get('successful_recoveries') or 0)} "
                    f"q_press={int(rs.get('queue_pressure_events') or 0)} "
                    f"r_press={int(rs.get('retry_pressure_events') or 0)} "
                    f"d_press={int(rs.get('deployment_pressure_events') or 0)}"
                )
            except Exception as exc:
                out.append(f"runtime_reliability: skip ({exc})")
            try:
                from app.runtime import runtime_continuity

                cont = runtime_continuity.summarize_runtime_continuity(st)
                out.append(
                    f"runtime_continuity: failures={int(cont.get('continuity_failures') or 0)} "
                    f"repairs={int(cont.get('continuity_repairs') or 0)} "
                    f"restart_rate={cont.get('restart_recovery_success_rate')} "
                    f"deploy_rate={cont.get('deployment_recovery_success_rate')}"
                )
            except Exception as exc:
                out.append(f"runtime_continuity: skip ({exc})")
            from app.runtime.backups.runtime_snapshots import list_runtime_backup_files
            from app.runtime.corruption.runtime_validation import scan_queue_duplicates_and_shape

            sig = scan_queue_duplicates_and_shape(st)
            out.append(f"queue_duplicate_signal: {int(sig.get('duplicate_queue_entries') or 0)}")
            try:
                nb = len(list_runtime_backup_files(limit=500))
                out.append(f"runtime_backups_on_disk: {nb}")
            except OSError as exc:
                out.append(f"runtime_backups_on_disk: skip ({exc})")
            qc = st.get("runtime_corruption_quarantine")
            if isinstance(qc, list) and qc:
                out.append(f"runtime_corruption_quarantine: {len(qc)} record(s)")
            pr_ep = execution_plan.prune_orphan_plans(st)
            if pr_ep:
                out.append(f"execution_plans: pruned {pr_ep} orphan plan(s)")
            stalled = 0
            if isinstance(tr, dict):
                cutoff = __import__("time").time() - 86400
                for t in tr.values():
                    if not isinstance(t, dict):
                        continue
                    if str(t.get("state")) != "running" or not t.get("execution_plan_id"):
                        continue
                    ua = t.get("updated_at")
                    if isinstance(ua, str) and ua[:4].isdigit():
                        try:
                            from datetime import datetime

                            dt = datetime.fromisoformat(ua.replace("Z", "+00:00"))
                            if dt.timestamp() < cutoff:
                                stalled += 1
                        except Exception:
                            pass
            if stalled:
                out.append(f"execution_stalled_hints: {stalled} task(s) running >24h")
        save_runtime_state(st)
        out.append("aethos.json: OK (reconciled stale gateway pid if any)")
    except Exception as exc:
        out.append(f"runtime_state: FAIL ({exc})")
    return out


def cmd_doctor(*, api_base: str) -> int:
    """Compile check + optional ``GET /api/v1/health`` + runtime parity checks."""
    root = _repo_root()
    print("== AethOS doctor (enterprise diagnostics) ==", file=sys.stderr)
    for label, rel in (("app", "app"), ("aethos_cli", "aethos_cli")):
        r = subprocess.run(
            [sys.executable, "-m", "compileall", "-q", rel],
            cwd=str(root),
            check=False,
        )
        if r.returncode != 0:
            print(f"compileall {label}: FAIL", file=sys.stderr)
            return 1
        print(f"compileall {label}: OK", file=sys.stderr)

    for ln in _runtime_doctor_messages():
        print(ln, file=sys.stderr)

    try:
        from app.services.mission_control.runtime_supervision import build_runtime_supervision

        sup = build_runtime_supervision()
        rs = sup.get("runtime_supervision") or {}
        print(f"runtime_supervision: api_owner={rs.get('api_owner_status')} sqlite={rs.get('sqlite_status')}", file=sys.stderr)
        print(f"telegram_mode: {rs.get('telegram_mode')}", file=sys.stderr)
        for c in rs.get("recommended_repairs") or []:
            print(f"  repair: {c}", file=sys.stderr)
        for c in (sup.get("runtime_process_supervision") or {}).get("conflicts") or []:
            print(f"process_conflict: {c}", file=sys.stderr)
    except Exception as exc:
        print(f"runtime_supervision: skip ({exc})", file=sys.stderr)

    base = (api_base or "").strip().rstrip("/")
    url = f"{base}/api/v1/health"
    try:
        req = urllib.request.Request(url, method="GET", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            code = resp.getcode()
            body = resp.read()[:4000].decode(errors="replace")
        print(f"health HTTP {code}: {body[:500]}", file=sys.stderr)
    except urllib.error.HTTPError as e:
        print(f"health HTTP {e.code} (API may be down or auth required)", file=sys.stderr)
        return 0
    except OSError as e:
        print(f"health: skip ({e})", file=sys.stderr)
    return 0
