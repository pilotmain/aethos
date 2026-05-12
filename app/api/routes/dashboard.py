# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(user_id: str = Query(default="")) -> str:
    safe_user_id = user_id.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Nexa Dashboard</title>
  <style>
    :root {{
      --bg: #f5efe3;
      --paper: #fffdf8;
      --ink: #1f2a2a;
      --muted: #6b746f;
      --line: #d7cfbf;
      --accent: #165d52;
      --accent-2: #ca6b2c;
      --soft: #e7f1ee;
      --warn: #7e2f2f;
      --shadow: 0 18px 45px rgba(31, 42, 42, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(202,107,44,0.12), transparent 28%),
        radial-gradient(circle at top right, rgba(22,93,82,0.10), transparent 24%),
        linear-gradient(180deg, #f7f1e7 0%, var(--bg) 100%);
    }}
    .shell {{
      max-width: 1440px;
      margin: 0 auto;
      padding: 28px;
    }}
    .hero {{
      display: grid;
      grid-template-columns: 1.3fr 0.9fr;
      gap: 18px;
      margin-bottom: 20px;
    }}
    .panel {{
      background: rgba(255, 253, 248, 0.92);
      border: 1px solid var(--line);
      border-radius: 22px;
      box-shadow: var(--shadow);
      padding: 20px;
      backdrop-filter: blur(8px);
    }}
    h1, h2, h3 {{
      margin: 0 0 10px;
      font-weight: 700;
      letter-spacing: 0.01em;
    }}
    h1 {{
      font-size: 34px;
      line-height: 1.05;
    }}
    p, li, code, input, button, textarea, select {{
      font-family: "Avenir Next", "Segoe UI", sans-serif;
    }}
    .lede {{
      color: var(--muted);
      max-width: 60ch;
      line-height: 1.5;
    }}
    .controls {{
      display: grid;
      grid-template-columns: 1fr auto auto;
      gap: 10px;
      align-items: center;
    }}
    input, textarea {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px 14px;
      background: #fffdfa;
      color: var(--ink);
    }}
    textarea {{
      min-height: 110px;
      resize: vertical;
    }}
    button {{
      border: none;
      border-radius: 999px;
      padding: 11px 16px;
      background: var(--accent);
      color: white;
      cursor: pointer;
      font-weight: 600;
    }}
    button.secondary {{
      background: #e7ddd0;
      color: var(--ink);
    }}
    button.warn {{
      background: var(--warn);
    }}
    .status {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 5px 10px;
      background: var(--soft);
      color: var(--accent);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}
    .grid {{
      display: grid;
      grid-template-columns: 1.1fr 0.9fr;
      gap: 18px;
    }}
    .stack {{
      display: grid;
      gap: 18px;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-top: 12px;
    }}
    .metric {{
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 14px;
      background: linear-gradient(180deg, rgba(255,255,255,0.85), rgba(245,239,227,0.8));
    }}
    .metric .label {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .metric .value {{
      margin-top: 8px;
      font-size: 26px;
      font-weight: 700;
    }}
    .section-head {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 10px;
    }}
    .list {{
      display: grid;
      gap: 12px;
      max-height: 520px;
      overflow: auto;
      padding-right: 4px;
    }}
    .item {{
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 14px;
      background: #fffdfa;
    }}
    .item-title {{
      font-weight: 700;
      margin-bottom: 6px;
    }}
    .meta {{
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }}
    .actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }}
    pre {{
      white-space: pre-wrap;
      background: #f7f3ea;
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 12px;
      overflow: auto;
    }}
    .split {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }}
    .flash {{
      min-height: 24px;
      color: var(--accent);
      font-weight: 600;
    }}
    .flash.error {{
      color: var(--warn);
    }}
    @media (max-width: 1100px) {{
      .hero, .grid, .split {{
        grid-template-columns: 1fr;
      }}
      .cards {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <div class="hero">
      <section class="panel">
        <div class="status">Local Operator Dashboard</div>
        <h1>Jobs, memory, check-ins, and approvals in one place.</h1>
        <p class="lede">This is the local control room for Nexa. Load one user, inspect the current state, forget stale reminders, approve jobs, and track Cursor handoffs without jumping between Telegram and SQLite.</p>
        <div class="controls">
          <input id="userId" value="{safe_user_id}" placeholder="User id, e.g. tg_1603429832" />
          <button id="loadBtn">Load User</button>
          <button id="refreshBtn" class="secondary">Refresh</button>
        </div>
        <div id="flash" class="flash"></div>
        <div class="cards">
          <div class="metric"><div class="label">Tasks</div><div id="metricTasks" class="value">0</div></div>
          <div class="metric"><div class="label">Pending Check-ins</div><div id="metricCheckins" class="value">0</div></div>
          <div class="metric"><div class="label">Jobs</div><div id="metricJobs" class="value">0</div></div>
        </div>
      </section>
      <section class="panel">
        <div class="section-head">
          <h2>Quick Actions</h2>
          <span class="status">Operator Tools</span>
        </div>
        <div class="stack">
          <div>
            <div class="meta">Forget a topic across memory, tasks, and check-ins.</div>
            <div class="controls" style="grid-template-columns: 1fr auto;">
              <input id="forgetQuery" placeholder="report, flight, task id, etc." />
              <button id="forgetBtn" class="warn">Forget</button>
            </div>
          </div>
          <div>
            <div class="meta">Append a rule to the soul file.</div>
            <div class="controls" style="grid-template-columns: 1fr auto;">
              <input id="soulRule" placeholder="Example: Never nag twice about the same revoked task." />
              <button id="soulBtn">Update Soul</button>
            </div>
          </div>
          <div>
            <div class="meta">Add a memory note directly from the console.</div>
            <div class="controls" style="grid-template-columns: 1fr auto;">
              <input id="memoryNoteInput" placeholder="Example: User prefers async check-ins over calls." />
              <button id="memoryNoteBtn">Add Note</button>
            </div>
          </div>
          <div>
            <div class="meta">Queue a safe smoke-test job that exercises the autonomous loop and returns a project report.</div>
            <button id="smokeTestBtn">Run Smoke Test Job</button>
          </div>
          <div>
            <div class="meta">Force the machine-side loops if you want an immediate refresh.</div>
            <div class="actions">
              <button id="handoffBtn" class="secondary">Process Handoffs</button>
              <button id="supervisorBtn" class="secondary">Run Supervisor</button>
              <button id="autoRefreshBtn" class="secondary">Auto Refresh: On</button>
            </div>
          </div>
        </div>
      </section>
    </div>

    <div class="grid">
      <div class="stack">
        <section class="panel">
          <div class="section-head">
            <h2>System Health</h2>
            <span class="status" id="healthStatus">Unknown</span>
          </div>
          <div id="healthBody" class="list" style="max-height: none;"></div>
        </section>

        <section class="panel">
          <div class="section-head">
            <h2>Jobs</h2>
            <span class="status" id="jobsStatus">Idle</span>
          </div>
          <div id="jobsList" class="list"></div>
        </section>

        <section class="panel">
          <div class="section-head">
            <h2>Tasks</h2>
            <span class="status">Live Queue</span>
          </div>
          <div id="tasksList" class="list"></div>
        </section>

        <section class="panel">
          <div class="section-head">
            <h2>Check-ins</h2>
            <span class="status">Follow-up State</span>
          </div>
          <div id="checkinsList" class="list"></div>
        </section>
      </div>

      <div class="stack">
        <section class="panel">
          <div class="section-head">
            <h2>Today’s Plan</h2>
            <span class="status" id="planStatus">No Data</span>
          </div>
          <div id="planBody" class="meta">Load a user to inspect the current plan.</div>
        </section>

        <section class="panel">
          <div class="section-head">
            <h2>Memory</h2>
            <span class="status">Persistent Context</span>
          </div>
          <div class="split">
            <div>
              <h3>Notes</h3>
              <div id="memoryNotes" class="list" style="max-height: 260px;"></div>
            </div>
            <div>
              <h3>Soul</h3>
              <pre id="soulBody">Load a user to view soul rules.</pre>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="section-head">
            <h2>Raw Snapshot</h2>
            <span class="status">Debug</span>
          </div>
          <pre id="rawState">No data loaded.</pre>
        </section>
      </div>
    </div>
  </div>

  <script>
    const state = {{ userId: "{safe_user_id}" }};
    let autoRefreshTimer = null;
    let autoRefreshEnabled = true;

    const $ = (id) => document.getElementById(id);
    const flash = (msg, isError = false) => {{
      const el = $("flash");
      el.textContent = msg;
      el.className = isError ? "flash error" : "flash";
    }};

    async function api(path, options = {{}}) {{
      const userId = $("userId").value.trim();
      if (!userId) throw new Error("Enter a user id first.");
      const headers = new Headers(options.headers || {{}});
      headers.set("X-User-Id", userId);
      if (!headers.has("Content-Type") && options.body) headers.set("Content-Type", "application/json");
      const res = await fetch(path, {{ ...options, headers }});
      if (!res.ok) {{
        const text = await res.text();
        throw new Error(text || `Request failed: ${{res.status}}`);
      }}
      const contentType = res.headers.get("content-type") || "";
      if (contentType.includes("application/json")) return res.json();
      return res.text();
    }}

    function itemActions(job) {{
      const actions = [];
      if (job.status === "needs_approval") {{
        actions.push(`<button onclick="actDecision(${{job.id}}, 'approve')">Approve</button>`);
        actions.push(`<button class="warn" onclick="actDecision(${{job.id}}, 'deny')">Deny</button>`);
      }}
      if (job.status === "ready_for_review") {{
        actions.push(`<button onclick="actReview(${{job.id}})">Approve Review</button>`);
      }}
      if (job.status === "needs_commit_approval") {{
        actions.push(`<button onclick="actCommit(${{job.id}})">Approve Commit</button>`);
      }}
      if (!["completed", "failed", "cancelled"].includes(job.status)) {{
        actions.push(`<button class="secondary" onclick="actCancel(${{job.id}})">Cancel</button>`);
      }}
      return actions.join("");
    }}

    function renderList(elId, rows, mapper, empty = "Nothing here right now.") {{
      const root = $(elId);
      if (!rows || rows.length === 0) {{
        root.innerHTML = `<div class="item"><div class="meta">${{empty}}</div></div>`;
        return;
      }}
      root.innerHTML = rows.map(mapper).join("");
    }}

    function renderJobs(rows) {{
      $("metricJobs").textContent = rows.length;
      renderList("jobsList", rows, (job) => `
        <div class="item">
          <div class="item-title">#${{job.id}} ${{job.command_type || job.kind}}</div>
          <div class="meta">status: ${{job.status}}<br>worker: ${{job.worker_type}}<br>title: ${{job.title || "-"}}</div>
          ${{job.cursor_task_path ? `<div class="meta">cursor file: ${{job.cursor_task_path}}</div>` : ""}}
          ${{job.result ? `<pre>${{job.result}}</pre>` : ""}}
          ${{job.error_message ? `<pre>${{job.error_message}}</pre>` : ""}}
          <div class="actions">${{itemActions(job)}}</div>
        </div>
      `, "No jobs yet.");
    }}

    function renderTasks(rows) {{
      $("metricTasks").textContent = rows.length;
      renderList("tasksList", rows, (task) => `
        <div class="item">
          <div class="item-title">#${{task.id}} ${{task.title}}</div>
          <div class="meta">status: ${{task.status}}<br>category: ${{task.category}}<br>priority: ${{task.priority_score}}</div>
          <div class="actions">
            <button onclick="completeTask(${{task.id}})">Complete</button>
            <button class="secondary" onclick="snoozeTask(${{task.id}}, 1)">Snooze 1d</button>
            <button class="warn" onclick="deleteTask(${{task.id}})">Delete</button>
          </div>
        </div>
      `, "No tasks found.");
    }}

    function renderCheckins(rows) {{
      $("metricCheckins").textContent = rows.length;
      renderList("checkinsList", rows, (row) => `
        <div class="item">
          <div class="item-title">#${{row.id}} task #${{row.task_id}}</div>
          <div class="meta">status: ${{row.status}}<br>scheduled: ${{row.scheduled_for}}</div>
          <pre>${{row.prompt_text}}</pre>
          <div class="actions">
            <button onclick="respondCheckin(${{row.id}}, 'done')">Mark Done</button>
            <button class="secondary" onclick="respondCheckin(${{row.id}}, 'not yet')">Not Yet</button>
            <button class="warn" onclick="cancelCheckin(${{row.id}})">Cancel</button>
          </div>
        </div>
      `, "No pending check-ins.");
    }}

    function renderMemory(stateData) {{
      $("soulBody").textContent = stateData.soul_markdown || "No soul rules yet.";
      renderList("memoryNotes", stateData.notes || [], (note) => `
        <div class="item">
          <div class="item-title">${{note.category}}</div>
          <div class="meta">${{note.summary}}</div>
          <textarea id="note-${{cssSafe(note.key)}}" style="margin-top: 10px;">${{note.content}}</textarea>
          <div class="actions">
            <button onclick="updateNote('${{jsSafe(note.key)}}')">Save Note</button>
            <button class="warn" onclick="deleteNote('${{jsSafe(note.key)}}')">Delete Note</button>
          </div>
        </div>
      `, "No saved notes.");
    }}

    function renderPlan(plan) {{
      if (!plan || !plan.tasks) {{
        $("planStatus").textContent = "No Plan";
        $("planBody").innerHTML = '<div class="meta">No plan found for today.</div>';
        return;
      }}
      $("planStatus").textContent = "Loaded";
      $("planBody").innerHTML = `
        <div class="item-title">${{plan.summary}}</div>
        <div class="meta">mode: ${{plan.mode}}<br>date: ${{plan.plan_date}}</div>
        <div class="list" style="margin-top: 12px; max-height: none;">
          ${{plan.tasks.map((task) => `<div class="item"><div class="item-title">${{task.title}}</div><div class="meta">status: ${{task.status}}</div></div>`).join("")}}
        </div>
      `;
    }}

    function renderHealth(health) {{
      const healthy = health && health.env_file_present && health.venv_present && health.codex_cli_exists && health.codex_login_ok;
      $("healthStatus").textContent = healthy ? "Ready" : "Attention";
      const rows = [
        ["Env file", health.env_file_present ? "present" : "missing"],
        ["Venv", health.venv_present ? "ready" : "missing"],
        ["API process", health.api_process?.running ? `running (${{health.api_process.pid}})` : "not running"],
        ["Bot process", health.bot_process?.running ? `running (${{health.bot_process.pid}})` : "not running"],
        ["Codex CLI", health.codex_cli_exists ? "found" : "missing"],
        ["Codex login", health.codex_login_ok ? (health.codex_login_stdout || "ok") : (health.codex_login_stderr || "not ready")],
        ["Git repo", health.is_git_repo ? "yes" : "no"],
        ["Operator poll", `${{health.operator_settings.poll_seconds}}s`],
      ];
      $("healthBody").innerHTML = rows.map(([label, value]) => `
        <div class="item">
          <div class="item-title">${{label}}</div>
          <div class="meta">${{value}}</div>
        </div>
      `).join("");
    }}

    async function loadDashboard() {{
      const userId = $("userId").value.trim();
      if (!userId) {{
        flash("Enter a user id first.", true);
        return;
      }}
      state.userId = userId;
      $("jobsStatus").textContent = "Loading";
      $("planStatus").textContent = "Loading";
      try {{
        const [me, jobs, tasks, checkins, memory, plan, health] = await Promise.all([
          api("/api/v1/auth/me"),
          api("/api/v1/jobs"),
          api("/api/v1/tasks"),
          api("/api/v1/checkins/pending"),
          api("/api/v1/web/memory/state"),
          api("/api/v1/plans/today").catch(() => null),
          api("/api/v1/internal/system-health"),
        ]);
        renderHealth(health);
        renderJobs(jobs);
        renderTasks(tasks);
        renderCheckins(checkins);
        renderMemory(memory);
        renderPlan(plan);
        $("rawState").textContent = JSON.stringify({{ me, jobs, tasks, checkins, memory, plan, health }}, null, 2);
        $("jobsStatus").textContent = "Loaded";
        flash(`Loaded local state for ${{me.user_id}}.`);
      }} catch (err) {{
        $("jobsStatus").textContent = "Error";
        $("planStatus").textContent = "Error";
        flash(err.message || String(err), true);
      }}
    }}

    async function actDecision(id, decision) {{
      try {{
        await api(`/api/v1/jobs/${{id}}/decision`, {{
          method: "POST",
          body: JSON.stringify({{ decision }})
        }});
        flash(`Updated job #${{id}} with decision: ${{decision}}.`);
        await loadDashboard();
      }} catch (err) {{
        flash(err.message || String(err), true);
      }}
    }}

    async function actCancel(id) {{
      try {{
        await api(`/api/v1/jobs/${{id}}/cancel`, {{ method: "POST" }});
        flash(`Cancelled job #${{id}}.`);
        await loadDashboard();
      }} catch (err) {{
        flash(err.message || String(err), true);
      }}
    }}

    async function actReview(id) {{
      try {{
        await api(`/api/v1/jobs/${{id}}/review-approve`, {{ method: "POST" }});
        flash(`Approved review for job #${{id}}.`);
        await loadDashboard();
      }} catch (err) {{
        flash(err.message || String(err), true);
      }}
    }}

    async function actCommit(id) {{
      try {{
        await api(`/api/v1/jobs/${{id}}/commit-approve`, {{ method: "POST" }});
        flash(`Approved commit for job #${{id}}.`);
        await loadDashboard();
      }} catch (err) {{
        flash(err.message || String(err), true);
      }}
    }}

    function jsSafe(value) {{
      return value.replace(/\\/g, "\\\\").replace(/'/g, "\\'");
    }}

    function cssSafe(value) {{
      return value.replace(/[^a-zA-Z0-9_-]/g, "_");
    }}

    async function completeTask(id) {{
      try {{
        await api(`/api/v1/tasks/${{id}}/complete`, {{ method: "POST" }});
        flash(`Completed task #${{id}}.`);
        await loadDashboard();
      }} catch (err) {{
        flash(err.message || String(err), true);
      }}
    }}

    async function snoozeTask(id, days) {{
      try {{
        await api(`/api/v1/tasks/${{id}}/snooze?days=${{days}}`, {{ method: "POST" }});
        flash(`Snoozed task #${{id}}.`);
        await loadDashboard();
      }} catch (err) {{
        flash(err.message || String(err), true);
      }}
    }}

    async function deleteTask(id) {{
      try {{
        await api(`/api/v1/tasks/${{id}}`, {{ method: "DELETE" }});
        flash(`Deleted task #${{id}}.`);
        await loadDashboard();
      }} catch (err) {{
        flash(err.message || String(err), true);
      }}
    }}

    async function respondCheckin(id, responseText) {{
      try {{
        await api(`/api/v1/checkins/respond`, {{
          method: "POST",
          body: JSON.stringify({{ checkin_id: id, response_text: responseText }})
        }});
        flash(`Updated check-in #${{id}}.`);
        await loadDashboard();
      }} catch (err) {{
        flash(err.message || String(err), true);
      }}
    }}

    async function cancelCheckin(id) {{
      try {{
        await api(`/api/v1/checkins/${{id}}/cancel`, {{ method: "POST" }});
        flash(`Cancelled check-in #${{id}}.`);
        await loadDashboard();
      }} catch (err) {{
        flash(err.message || String(err), true);
      }}
    }}

    async function updateNote(key) {{
      try {{
        const value = $(`note-${{cssSafe(key)}}`).value.trim();
        if (!value) throw new Error("Note content cannot be empty.");
        await api(`/api/v1/web/memory/notes`, {{
          method: "PATCH",
          body: JSON.stringify({{ key, content: value }})
        }});
        flash("Memory note updated.");
        await loadDashboard();
      }} catch (err) {{
        flash(err.message || String(err), true);
      }}
    }}

    async function deleteNote(key) {{
      try {{
        await api(`/api/v1/web/memory/notes/delete`, {{
          method: "POST",
          body: JSON.stringify({{ key }})
        }});
        flash("Memory note deleted.");
        await loadDashboard();
      }} catch (err) {{
        flash(err.message || String(err), true);
      }}
    }}

    $("loadBtn").addEventListener("click", loadDashboard);
    $("refreshBtn").addEventListener("click", loadDashboard);
    $("memoryNoteBtn").addEventListener("click", async () => {{
      try {{
        const content = $("memoryNoteInput").value.trim();
        if (!content) throw new Error("Enter a memory note first.");
        await api("/api/v1/web/memory/remember", {{
          method: "POST",
          body: JSON.stringify({{ content, category: "operator_note" }})
        }});
        $("memoryNoteInput").value = "";
        flash("Memory note added.");
        await loadDashboard();
      }} catch (err) {{
        flash(err.message || String(err), true);
      }}
    }});
    $("smokeTestBtn").addEventListener("click", async () => {{
      try {{
        const job = await api("/api/v1/jobs", {{
          method: "POST",
          body: JSON.stringify({{
            kind: "local_action",
            worker_type: "local_tool",
            title: "Smoke test project report",
            instruction: "Summarize the current project state and generate a safe report task for the operator dashboard.",
            command_type: "summarize-project",
            source: "dashboard",
            approval_required: false,
            payload_json: {{ smoke_test: true }}
          }})
        }});
        flash(`Queued smoke test job #${{job.id}}.`);
        await loadDashboard();
      }} catch (err) {{
        flash(err.message || String(err), true);
      }}
    }});
    $("forgetBtn").addEventListener("click", async () => {{
      try {{
        const query = $("forgetQuery").value.trim();
        if (!query) throw new Error("Enter something to forget first.");
        const result = await api("/api/v1/web/memory/forget", {{
          method: "POST",
          body: JSON.stringify({{ query }})
        }});
        flash(`Forgot '${'{'}result.query{'}'}'. Removed ${{result.deleted_tasks}} tasks and cancelled ${{result.cancelled_checkins}} check-ins.`);
        await loadDashboard();
      }} catch (err) {{
        flash(err.message || String(err), true);
      }}
    }});
    $("soulBtn").addEventListener("click", async () => {{
      try {{
        const rule = $("soulRule").value.trim();
        if (!rule) throw new Error("Enter a soul rule first.");
        const current = await api("/api/v1/web/memory/state");
        await api("/api/v1/web/memory/soul", {{
          method: "PUT",
          body: JSON.stringify({{ content: `${{current.soul_markdown}}\\n- ${{rule}}` }})
        }});
        flash("Soul updated.");
        $("soulRule").value = "";
        await loadDashboard();
      }} catch (err) {{
        flash(err.message || String(err), true);
      }}
    }});
    $("handoffBtn").addEventListener("click", async () => {{
      try {{
        const data = await api("/api/v1/internal/process-job-handoffs", {{ method: "POST" }});
        flash(`Processed ${{data.processed}} handoff(s).`);
        await loadDashboard();
      }} catch (err) {{
        flash(err.message || String(err), true);
      }}
    }});
    $("supervisorBtn").addEventListener("click", async () => {{
      try {{
        const data = await api("/api/v1/internal/process-supervisor-cycle", {{ method: "POST" }});
        flash(`Supervisor ran. Auto-reviewed: ${{(data.auto_reviewed || []).length}}, auto-committed: ${{(data.auto_committed || []).length}}.`);
        await loadDashboard();
      }} catch (err) {{
        flash(err.message || String(err), true);
      }}
    }});
    $("autoRefreshBtn").addEventListener("click", () => {{
      autoRefreshEnabled = !autoRefreshEnabled;
      $("autoRefreshBtn").textContent = `Auto Refresh: ${{autoRefreshEnabled ? "On" : "Off"}}`;
      if (autoRefreshEnabled) {{
        autoRefreshTimer = setInterval(loadDashboard, 15000);
      }} else if (autoRefreshTimer) {{
        clearInterval(autoRefreshTimer);
        autoRefreshTimer = null;
      }}
    }});

    if (autoRefreshEnabled) autoRefreshTimer = setInterval(loadDashboard, 15000);
    if (state.userId) loadDashboard();
  </script>
</body>
</html>"""
