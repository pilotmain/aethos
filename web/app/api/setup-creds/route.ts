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

export async function GET() {
  try {
    const raw = await readFile(credsPath(), "utf8");
    const j = JSON.parse(raw) as Record<string, unknown>;
    if (!j || typeof j !== "object") {
      return NextResponse.json({});
    }
    return NextResponse.json(j);
  } catch {
    return NextResponse.json({});
  }
}
