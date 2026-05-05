"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { Download, Loader2, Upload } from "lucide-react";

interface ExportImportProps {
  onExport: () => Promise<void>;
  onImport: (file: File) => Promise<void>;
}

export function ExportImport({ onExport, onImport }: ExportImportProps) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const runExport = async () => {
    setBusy(true);
    setMessage(null);
    try {
      await onExport();
      setMessage("Export downloaded.");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const runImport = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    setMessage(null);
    try {
      await onImport(file);
      setMessage("Import applied (merged ui_preferences when valid).");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="border-zinc-800 bg-zinc-900/40">
      <CardHeader>
        <CardTitle className="text-zinc-50">Export / import</CardTitle>
        <CardDescription>
          Exports privacy mode + ui_preferences (no API keys). Imports must include a <code className="text-zinc-400">ui_preferences</code>{" "}
          object from a prior export.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" className="border-zinc-700" disabled={busy} onClick={() => void runExport()}>
            {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}
            Export JSON
          </Button>
          <label
            className={cn(
              "inline-flex h-10 cursor-pointer items-center justify-center whitespace-nowrap rounded-md border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm font-medium text-zinc-100 hover:bg-zinc-800",
              busy && "pointer-events-none opacity-50",
            )}
          >
            {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Upload className="mr-2 h-4 w-4" />}
            Import JSON
            <input
              type="file"
              accept="application/json,.json"
              className="hidden"
              disabled={busy}
              onChange={(e) => void runImport(e.target.files?.[0])}
            />
          </label>
        </div>
        {message ? <p className="text-sm text-zinc-400">{message}</p> : null}
      </CardContent>
    </Card>
  );
}
