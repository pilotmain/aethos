# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""``nexa status`` — quick HTTP health checks against the configured API base."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def _base_url() -> str:
    return (
        os.environ.get("NEXA_API_BASE")
        or os.environ.get("API_BASE_URL")
        or "http://127.0.0.1:8010"
    ).rstrip("/")


def cmd_status() -> int:
    base = _base_url()
    paths = (
        ("/api/v1/health", "FastAPI health"),
        ("/api/v1/system/health", "System health"),
    )
    ok_any = False
    print(f"API base: {base}\n")
    for path, label in paths:
        url = f"{base}{path}"
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                print(f"✓ {label}  HTTP {resp.getcode()}  {path}")
                try:
                    print(json.dumps(json.loads(body), indent=2)[:4000])
                except json.JSONDecodeError:
                    print(body[:2000])
                ok_any = ok_any or resp.getcode() == 200
        except urllib.error.HTTPError as exc:
            print(f"✗ {label}  HTTP {exc.code}  {path}", file=sys.stderr)
            print(exc.read().decode("utf-8", errors="replace")[:800], file=sys.stderr)
        except urllib.error.URLError as exc:
            print(f"✗ {label}  offline — {exc.reason}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001
            print(f"✗ {label}  error — {exc}", file=sys.stderr)
        print()
    try:
        from app.core.paths import get_runtime_state_path

        rp = get_runtime_state_path()
        if rp.is_file():
            print("— Persistent runtime (~/.aethos/aethos.json) —\n")
            try:
                doc = json.loads(rp.read_text(encoding="utf-8"))
                gw = doc.get("gateway") or {}
                print(f"runtime_id:     {doc.get('runtime_id', '')}")
                print(f"last_started:   {doc.get('last_started_at', '')}")
                print(f"gateway host:   {gw.get('host', '')}")
                print(f"gateway port:   {gw.get('port', '')}")
                print(f"gateway running:{gw.get('running', '')}")
                print(f"gateway pid:    {gw.get('pid', '')}")
                print(f"last_heartbeat: {gw.get('last_heartbeat', '')}")
                ws = (doc.get("workspace") or {}).get("root", "")
                print(f"workspace:      {ws}")
                sess = doc.get("sessions") or []
                agents = doc.get("agents") or []
                print(f"sessions:       {len(sess) if isinstance(sess, list) else 0}")
                print(f"agents:         {len(agents) if isinstance(agents, list) else 0}")
                tr = doc.get("task_registry") or {}
                if isinstance(tr, dict):
                    active = sum(1 for t in tr.values() if isinstance(t, dict) and str(t.get("state")) == "running")
                    recovering = sum(
                        1 for t in tr.values() if isinstance(t, dict) and str(t.get("state")) == "recovering"
                    )
                    queued = sum(1 for t in tr.values() if isinstance(t, dict) and str(t.get("state")) == "queued")
                    retrying_tasks = sum(
                        1 for t in tr.values() if isinstance(t, dict) and str(t.get("state")) == "retrying"
                    )
                    print("— Orchestration runtime —")
                    eq = doc.get("execution_queue") or []
                    rq = doc.get("recovery_queue") or []
                    sch = (doc.get("orchestration") or {}).get("scheduler") or {}
                    gw_hb = gw.get("last_heartbeat", "")
                    deps = doc.get("deployments") or []
                    print(f"scheduler ticks: {sch.get('ticks', '')}  last_tick: {sch.get('last_tick', '')}")
                    print(f"active tasks:    {active}  queued(state): {queued}  recovering: {recovering}  retrying: {retrying_tasks}")
                    print(f"execution_queue: {len(eq) if isinstance(eq, list) else 0}  recovery_queue: {len(rq) if isinstance(rq, list) else 0}")
                    print(f"gateway hb:      {gw_hb}")
                    print(f"deployments:     {len(deps) if isinstance(deps, list) else 0}")
                    print(f"runtime health:  gateway_running={gw.get('running')} scheduler_running={sch.get('running')}")
                    ex = doc.get("execution") or {}
                    pl = ex.get("plans") or {}
                    sup_ex = ex.get("supervisor") or {}
                    cpx = ex.get("checkpoints") or {}
                    retry_steps = 0
                    if isinstance(pl, dict):
                        for p in pl.values():
                            if not isinstance(p, dict):
                                continue
                            for s in p.get("steps") or []:
                                if isinstance(s, dict) and str(s.get("status")) == "retrying":
                                    retry_steps += 1
                    rec_ev = (doc.get("recovery") or {}).get("events") or []
                    chk_count = sum(len(v) for v in cpx.values()) if isinstance(cpx, dict) else 0
                    print("— Autonomous execution —")
                    print(f"execution graphs: {len(pl) if isinstance(pl, dict) else 0}")
                    print(f"retrying steps:   {retry_steps}")
                    print(f"checkpoint keys:  {chk_count}")
                    print(f"supervisor ticks: {sup_ex.get('ticks', '')}  last_error: {sup_ex.get('last_error', '')}")
                    print(f"recovery events:  {len(rec_ev) if isinstance(rec_ev, list) else 0}")
                    wf_active = wf_done = wf_fail = 0
                    if isinstance(tr, dict):
                        for t in tr.values():
                            if not isinstance(t, dict) or str(t.get("type") or "") != "workflow":
                                continue
                            stwf = str(t.get("state") or "")
                            if stwf in ("queued", "scheduled", "running", "waiting", "retrying", "recovering"):
                                wf_active += 1
                            elif stwf == "completed":
                                wf_done += 1
                            elif stwf == "failed":
                                wf_fail += 1
                    print("— Tool workflows —")
                    print(f"workflow tasks:   active={wf_active}  completed={wf_done}  failed={wf_fail}")
                    rs_doc = doc.get("runtime_sessions") or {}
                    if isinstance(rs_doc, dict):
                        print(f"runtime_sessions: {len(rs_doc)}")
                print()
            except Exception as exc:  # noqa: BLE001
                print(f"(could not parse runtime file: {exc})", file=sys.stderr)
            print()
        else:
            print("— Persistent runtime —\n(no ~/.aethos/aethos.json yet; start the API once)\n")
    except Exception as exc:  # noqa: BLE001
        print(f"(runtime status skipped: {exc})", file=sys.stderr)
    return 0 if ok_any else 1


def try_post_install_health_hint() -> bool:
    """
    Lightweight GET /api/v1/health after setup — does not fail install if offline.

    Returns True if API responds with HTTP 200.
    """
    base = _base_url()
    url = f"{base}/api/v1/health"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            if resp.getcode() == 200:
                print(f"\n✓ API already reachable at {base} (great — stack may be running).\n")
                return True
    except Exception:
        pass
    print(
        f"\nℹ API not reachable yet at {base} — expected until you run:\n"
        "    python -m aethos_cli serve\n",
        file=sys.stderr,
    )
    return False


__all__ = ["cmd_status", "try_post_install_health_hint"]
