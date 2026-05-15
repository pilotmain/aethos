import { readFile } from "fs/promises";
import os from "os";
import path from "path";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

function credsPath(): string {
  const override = (process.env.AETHOS_SETUP_CREDS_FILE || "").trim();
  if (override) {
    return override;
  }
  return path.join(os.tmpdir(), "aethos_creds.json");
}

function parseDotenv(content: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const rawLine of content.split("\n")) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) continue;
    const eq = line.indexOf("=");
    const k = line.slice(0, eq).trim();
    let v = line.slice(eq + 1).trim();
    if (
      (v.startsWith('"') && v.endsWith('"')) ||
      (v.startsWith("'") && v.endsWith("'"))
    ) {
      v = v.slice(1, -1);
    }
    if (k) out[k] = v;
  }
  return out;
}

async function readEnvFile(p: string): Promise<Record<string, string>> {
  try {
    return parseDotenv(await readFile(p, "utf8"));
  } catch {
    return {};
  }
}

/** Match ``app.core.setup_creds_file.read_setup_creds_merged_dict`` — dotenv wins over JSON snapshot. */
export async function GET() {
  let json: Record<string, unknown> = {};
  try {
    const raw = await readFile(credsPath(), "utf8");
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    if (parsed && typeof parsed === "object") json = parsed;
  } catch {
    /* no snapshot */
  }

  const out: Record<string, string> = {};
  const setIf = (key: string, val: unknown) => {
    if (typeof val === "string" && val.trim()) out[key] = val.trim();
  };
  setIf("api_base", json.api_base);
  setIf("user_id", json.user_id);
  setIf("bearer_token", json.bearer_token);

  const envPaths = [
    path.join(process.cwd(), "..", ".env"),
    path.join(process.cwd(), ".env"),
    path.join(os.homedir(), ".aethos", ".env"),
  ];

  for (const envPath of envPaths) {
    const blob = await readEnvFile(envPath);
    const apiBase = (blob.API_BASE_URL || "").trim();
    if (apiBase) out.api_base = apiBase.replace(/\/$/, "");
    const tok = (blob.NEXA_WEB_API_TOKEN || "").trim();
    if (tok) out.bearer_token = tok;
    const uid = (blob.TEST_X_USER_ID || blob.X_USER_ID || "").trim();
    if (uid) out.user_id = uid;
  }

  return NextResponse.json(out);
}
