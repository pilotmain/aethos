"use client";

import { useEffect, useState } from "react";

import type { SystemConfig } from "@/types/mission-control";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";

interface SystemSettingsProps {
  config: SystemConfig;
  onSave: (config: Partial<SystemConfig>) => Promise<void>;
}

export function SystemSettings({ config, onSave }: SystemSettingsProps) {
  const [workspaceRoot, setWorkspaceRoot] = useState(config.workspace_root);
  const [dataDir, setDataDir] = useState(config.data_dir);
  const [sandboxMode, setSandboxMode] = useState(config.sandbox_mode);
  const [networkPolicy, setNetworkPolicy] = useState(config.network_policy_strict);
  const [approvalsEnabled, setApprovalsEnabled] = useState(config.approvals_enabled);
  const [autonomousMode, setAutonomousMode] = useState(config.autonomous_mode);
  const [logLevel, setLogLevel] = useState<SystemConfig["log_level"]>(config.log_level);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setWorkspaceRoot(config.workspace_root);
    setDataDir(config.data_dir);
    setSandboxMode(config.sandbox_mode);
    setNetworkPolicy(config.network_policy_strict);
    setApprovalsEnabled(config.approvals_enabled);
    setAutonomousMode(config.autonomous_mode);
    setLogLevel(config.log_level);
  }, [config]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave({
        workspace_root: workspaceRoot,
        data_dir: dataDir,
        sandbox_mode: sandboxMode,
        network_policy_strict: networkPolicy,
        approvals_enabled: approvalsEnabled,
        autonomous_mode: autonomousMode,
        log_level: logLevel,
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="border-zinc-800 bg-zinc-900/40">
      <CardHeader>
        <CardTitle className="text-zinc-50">System configuration</CardTitle>
        <CardDescription>
          Values persist under ui_preferences.advanced_system. Execution policies on the host may still read environment
          variables — treat these as operator notes unless wired server-side.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="workspace-root" className="text-zinc-200">
            Workspace root (note)
          </Label>
          <Input
            id="workspace-root"
            className="border-zinc-800 bg-zinc-950"
            value={workspaceRoot}
            onChange={(e) => setWorkspaceRoot(e.target.value)}
            placeholder="~/nexa-projects"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="data-dir" className="text-zinc-200">
            Data directory (note)
          </Label>
          <Input
            id="data-dir"
            className="border-zinc-800 bg-zinc-950"
            value={dataDir}
            onChange={(e) => setDataDir(e.target.value)}
          />
        </div>

        <div className="flex items-center justify-between gap-4 rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-2">
          <div className="space-y-0.5">
            <Label className="text-zinc-200">Sandbox mode</Label>
            <p className="text-xs text-zinc-500">Prefer isolated execution where supported.</p>
          </div>
          <Switch checked={sandboxMode} onCheckedChange={setSandboxMode} />
        </div>

        <div className="flex items-center justify-between gap-4 rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-2">
          <div className="space-y-0.5">
            <Label className="text-zinc-200">Strict network policy</Label>
            <p className="text-xs text-zinc-500">Intent flag for future allowlisting checks.</p>
          </div>
          <Switch checked={networkPolicy} onCheckedChange={setNetworkPolicy} />
        </div>

        <div className="flex items-center justify-between gap-4 rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-2">
          <div className="space-y-0.5">
            <Label className="text-zinc-200">Approvals required</Label>
            <p className="text-xs text-zinc-500">Mirror human-in-the-loop posture for tooling.</p>
          </div>
          <Switch checked={approvalsEnabled} onCheckedChange={setApprovalsEnabled} />
        </div>

        <div className="flex items-center justify-between gap-4 rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-2">
          <div className="space-y-0.5">
            <Label className="text-zinc-200">Autonomous mode</Label>
            <p className="text-xs text-zinc-500">Document intent only until enforced centrally.</p>
          </div>
          <Switch checked={autonomousMode} onCheckedChange={setAutonomousMode} />
        </div>

        <div className="space-y-2">
          <Label className="text-zinc-200">Log level (preference)</Label>
          <Select value={logLevel} onValueChange={(v) => setLogLevel(v as SystemConfig["log_level"])}>
            <SelectTrigger className="border-zinc-800 bg-zinc-950">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="debug">Debug</SelectItem>
              <SelectItem value="info">Info</SelectItem>
              <SelectItem value="warning">Warning</SelectItem>
              <SelectItem value="error">Error</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <Button type="button" onClick={() => void handleSave()} disabled={saving}>
          {saving ? "Saving…" : "Save changes"}
        </Button>
      </CardContent>
    </Card>
  );
}
