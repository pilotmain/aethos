"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AlertTriangle, Trash2 } from "lucide-react";

interface DangerZoneProps {
  onReset: () => Promise<void>;
  onDeleteWorkspace: () => Promise<void>;
}

export function DangerZone({ onReset, onDeleteWorkspace }: DangerZoneProps) {
  const [resetText, setResetText] = useState("");
  const [deleteText, setDeleteText] = useState("");
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const handleReset = async () => {
    if (resetText !== "RESET") return;
    setLoading(true);
    setMsg(null);
    try {
      await onReset();
      setMsg("Advanced UI preferences cleared (API keys unchanged).");
      setResetText("");
      setShowResetConfirm(false);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (deleteText !== "DELETE WORKSPACE") return;
    setLoading(true);
    setMsg(null);
    try {
      await onDeleteWorkspace();
      setDeleteText("");
      setShowDeleteConfirm(false);
      setMsg("Acknowledged. Coordinate workspace teardown with your AethOS operator / host.");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <Card className="border-red-900/40 bg-red-950/20">
        <CardHeader>
          <CardTitle className="text-red-300">Danger zone</CardTitle>
          <CardDescription className="text-red-200/70">
            Destructive or irreversible actions. There is no single API to wipe an entire AethOS workspace from this UI — server
            operators must remove database volumes or tenant data on the host.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {msg ? <p className="text-sm text-zinc-300">{msg}</p> : null}

          <div className="flex flex-col gap-3 rounded-lg border border-red-900/50 bg-red-950/30 p-4 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="flex items-center gap-2 font-medium text-red-200">
                <AlertTriangle className="h-4 w-4" />
                Reset advanced UI preferences
              </div>
              <p className="text-sm text-red-200/80">Clears Mission Control advanced_* / integrations_ui prefs — not LLM BYOK keys.</p>
            </div>
            <Button type="button" variant="destructive" className="shrink-0" onClick={() => setShowResetConfirm((v) => !v)}>
              Reset
            </Button>
          </div>

          {showResetConfirm ? (
            <div className="rounded-lg border border-red-900/50 bg-zinc-950 p-4">
              <Label className="text-zinc-200">Type RESET to confirm</Label>
              <div className="mt-2 flex flex-wrap gap-2">
                <Input
                  placeholder="RESET"
                  className="max-w-xs border-zinc-800 bg-zinc-900"
                  value={resetText}
                  onChange={(e) => setResetText(e.target.value)}
                />
                <Button type="button" variant="destructive" disabled={resetText !== "RESET" || loading} onClick={() => void handleReset()}>
                  Confirm reset
                </Button>
              </div>
            </div>
          ) : null}

          <div className="flex flex-col gap-3 rounded-lg border border-red-900/50 bg-red-950/30 p-4 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="flex items-center gap-2 font-medium text-red-200">
                <Trash2 className="h-4 w-4" />
                Delete workspace (informational)
              </div>
              <p className="text-sm text-red-200/80">
                Confirms you understand host-side deletion is required; this button does not call a destructive API.
              </p>
            </div>
            <Button type="button" variant="destructive" className="shrink-0" onClick={() => setShowDeleteConfirm((v) => !v)}>
              Acknowledge
            </Button>
          </div>

          {showDeleteConfirm ? (
            <div className="rounded-lg border border-red-900/50 bg-zinc-950 p-4">
              <Label className="text-zinc-200">Type DELETE WORKSPACE to confirm you read the warning</Label>
              <div className="mt-2 flex flex-wrap gap-2">
                <Input
                  placeholder="DELETE WORKSPACE"
                  className="max-w-xs border-zinc-800 bg-zinc-900"
                  value={deleteText}
                  onChange={(e) => setDeleteText(e.target.value)}
                />
                <Button
                  type="button"
                  variant="destructive"
                  disabled={deleteText !== "DELETE WORKSPACE" || loading}
                  onClick={() => void handleDelete()}
                >
                  Done
                </Button>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
