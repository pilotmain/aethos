#!/usr/bin/env node
/**
 * Smoke check: required files exist; optionally GET the dev server.
 * Run a full build with: cd web && npm run build:clean
 */
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const webRoot = join(__dirname, "..");
const mustExist = [
  "app/page.tsx",
  "app/login/page.tsx",
  "app/globals.css",
  "app/layout.tsx",
  "components/nexa/WorkspaceApp.tsx",
  "components/nexa/JobInlineCard.tsx",
  "lib/api.ts",
  "lib/config.ts",
  "tailwind.config.ts",
  "postcss.config.mjs",
];

let failed = false;
for (const rel of mustExist) {
  const p = join(webRoot, rel);
  if (!existsSync(p)) {
    console.error(`[smoke] missing: ${rel}`);
    failed = true;
  }
}

if (!failed) {
  const pkg = JSON.parse(readFileSync(join(webRoot, "package.json"), "utf8"));
  if (!pkg.name || !pkg.scripts?.build) {
    console.error("[smoke] package.json missing name or build script");
    failed = true;
  }
  if (!pkg.scripts?.["build:clean"]) {
    console.error("[smoke] package.json should define script build:clean");
    failed = true;
  }
}

const base = process.env.SMOKE_WEB_URL || "http://127.0.0.1:3000";
try {
  const res = await fetch(base, { signal: AbortSignal.timeout(3000) });
  console.log(`[smoke] GET ${base} → ${res.status}`);
} catch (e) {
  console.log(`[smoke] GET ${base} skipped (${(e).message || e})`);
}

process.exit(failed ? 1 : 0);
