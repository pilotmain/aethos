"""Static file bundles for multi-step goal plans (workspace-scoped; no shell)."""

from __future__ import annotations

from typing import Any


def slugify_phrase(phrase: str, *, max_len: int = 48) -> str:
    s = (phrase or "").strip().lower()
    out = []
    for ch in s:
        if ch.isalnum():
            out.append(ch)
        elif ch in (" ", "-", "_"):
            out.append("-")
    slug = "".join(out).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return (slug[:max_len] or "app").rstrip("-")


def todo_static_bundle(slug: str) -> list[dict[str, Any]]:
    """Minimal static todo UI (localStorage) under ``{slug}-app/``."""
    safe = slugify_phrase(slug) or "app"
    base = f"{safe}-app"
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{safe} todo</title>
  <link rel="stylesheet" href="styles.css" />
</head>
<body>
  <main class="wrap">
    <h1>{safe} — todos</h1>
    <form id="add-form">
      <input id="task" type="text" placeholder="New task" autocomplete="off" />
      <button type="submit">Add</button>
    </form>
    <ul id="list"></ul>
  </main>
  <script src="app.js"></script>
</body>
</html>
"""
    css = """body { font-family: system-ui, sans-serif; margin: 2rem; background: #0f172a; color: #e2e8f0; }
.wrap { max-width: 520px; margin: 0 auto; }
input { width: 70%; padding: 0.5rem; border-radius: 6px; border: 1px solid #334155; background: #020617; color: inherit; }
button { padding: 0.5rem 0.75rem; border-radius: 6px; border: 0; background: #38bdf8; color: #0f172a; cursor: pointer; }
ul { list-style: none; padding: 0; }
li { padding: 0.5rem 0; border-bottom: 1px solid #1e293b; display: flex; justify-content: space-between; gap: 0.5rem; }
"""
    js = """const form = document.getElementById("add-form");
const input = document.getElementById("task");
const list = document.getElementById("list");
const storageKey = "nexa-todo-items";
let items = [];
try { items = JSON.parse(localStorage.getItem(storageKey) || "[]"); } catch { items = []; }
function save() { localStorage.setItem(storageKey, JSON.stringify(items)); render(); }
function render() {
  list.innerHTML = "";
  items.forEach((text, i) => {
    const li = document.createElement("li");
    const span = document.createElement("span");
    span.textContent = text;
    const toggle = document.createElement("button");
    toggle.textContent = "Done";
    toggle.onclick = () => { items.splice(i, 1); save(); };
    li.appendChild(span);
    li.appendChild(toggle);
    list.appendChild(li);
  });
}
form.addEventListener("submit", (e) => {
  e.preventDefault();
  const v = (input.value || "").trim();
  if (!v) return;
  items.push(v);
  input.value = "";
  save();
});
render();
"""
    readme = f"# {safe} todo\n\nOpen `{base}/index.html` in a browser.\n"
    return [
        {"filename": f"{base}/index.html", "content": html},
        {"filename": f"{base}/styles.css", "content": css},
        {"filename": f"{base}/app.js", "content": js},
        {"filename": f"{base}/README.md", "content": readme},
    ]


def todo_backend_node_bundle(slug: str) -> list[dict[str, Any]]:
    """Tiny Node ``http`` + JSON file store (no npm required to inspect; run with ``node server.js``)."""
    safe = slugify_phrase(slug) or "app"
    base = f"{safe}-app"
    readme = f"""# Backend ({safe})

JSON file database at `data/todos.json`. Run:

```bash
cd {base}/backend && node server.js
```

Then open http://127.0.0.1:3847 — the static UI in the parent folder can be wired to this API later.
"""
    server = r"""const http = require("http");
const fs = require("fs");
const path = require("path");
const root = __dirname;
const dataDir = path.join(root, "data");
const dataFile = path.join(dataDir, "todos.json");
function readTodos() {
  try {
    const raw = fs.readFileSync(dataFile, "utf8");
    return JSON.parse(raw);
  } catch {
    return [];
  }
}
function writeTodos(rows) {
  fs.mkdirSync(dataDir, { recursive: true });
  fs.writeFileSync(dataFile, JSON.stringify(rows, null, 2), "utf8");
}
const port = process.env.PORT ? Number(process.env.PORT) : 3847;
http
  .createServer((req, res) => {
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type");
    res.setHeader("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS");
    if (req.method === "OPTIONS") {
      res.writeHead(204);
      return res.end();
    }
    if (req.method === "GET" && req.url === "/todos") {
      res.writeHead(200, { "Content-Type": "application/json" });
      return res.end(JSON.stringify(readTodos()));
    }
    if (req.method === "POST" && req.url === "/todos") {
      let body = "";
      req.on("data", (c) => (body += c));
      req.on("end", () => {
        let title = "";
        try {
          title = String(JSON.parse(body || "{}").title || "").trim();
        } catch {
          title = "";
        }
        if (!title) {
          res.writeHead(400, { "Content-Type": "application/json" });
          return res.end(JSON.stringify({ error: "title required" }));
        }
        const rows = readTodos();
        rows.push({ id: String(Date.now()), title });
        writeTodos(rows);
        res.writeHead(201, { "Content-Type": "application/json" });
        return res.end(JSON.stringify(rows[rows.length - 1]));
      });
      return;
    }
    res.writeHead(404, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: "not_found" }));
  })
  .listen(port, () => {
    // eslint-disable-next-line no-console
    console.log("todo backend on http://127.0.0.1:" + port);
  });
"""
    return [
        {"filename": f"{base}/backend/README.md", "content": readme},
        {"filename": f"{base}/backend/server.js", "content": server},
        {"filename": f"{base}/backend/data/.gitkeep", "content": ""},
    ]


__all__ = ["slugify_phrase", "todo_backend_node_bundle", "todo_static_bundle"]
