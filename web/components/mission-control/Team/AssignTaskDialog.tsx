"use client";

import { useState } from "react";
import { Send } from "lucide-react";

import { formatMissionControlApiError } from "@/lib/api";
import {
  createAgentAssignment,
  type AgentAssignmentCreateResponse,
} from "@/lib/api/assignments";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

const PRIORITY_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "low", label: "Low" },
  { value: "normal", label: "Normal" },
  { value: "high", label: "High" },
];

export interface AssignTaskDialogProps {
  /** Agent handle to dispatch to (e.g. ``security_agent``); required for the API call. */
  agentHandle: string;
  /** Optional display name; falls back to ``agentHandle``. */
  agentDisplayName?: string;
  /** Domain shown for context in the dialog header. */
  agentDomain?: string;
  /** Disable the trigger entirely (e.g. when the agent is busy). */
  disabled?: boolean;
  /** Tooltip shown when ``disabled`` is true. */
  disabledReason?: string;
  /** Called after a successful create. ``response.auto_dispatch`` is present when the API auto-ran the work. */
  onAssigned?: (response: AgentAssignmentCreateResponse) => void | Promise<void>;
}

export function AssignTaskDialog({
  agentHandle,
  agentDisplayName,
  agentDomain,
  disabled,
  disabledReason,
  onAssigned,
}: AssignTaskDialogProps) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("normal");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const display = agentDisplayName?.trim() || agentHandle;

  const reset = () => {
    setTitle("");
    setDescription("");
    setPriority("normal");
    setError(null);
  };

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const t = title.trim();
    if (!t) {
      setError("Task title is required.");
      return;
    }
    if (!agentHandle) {
      setError("Missing agent handle.");
      return;
    }
    setSubmitting(true);
    try {
      const response = await createAgentAssignment({
        assigned_to_handle: agentHandle,
        title: t,
        description: description.trim(),
        priority,
      });
      reset();
      setOpen(false);
      if (onAssigned) {
        await onAssigned(response);
      }
    } catch (err) {
      setError(formatMissionControlApiError(err instanceof Error ? err.message : String(err)));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) reset();
      }}
    >
      <DialogTrigger asChild>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled}
          title={disabled ? disabledReason : `Assign task to @${display}`}
          className="shrink-0"
        >
          <Send className="mr-2 h-3.5 w-3.5" aria-hidden />
          Assign task
        </Button>
      </DialogTrigger>
      <DialogContent className="border-zinc-800 bg-zinc-950">
        <DialogHeader>
          <DialogTitle>Assign task to @{display}</DialogTitle>
          <DialogDescription>
            Calls{" "}
            <code className="font-mono text-xs text-zinc-400">POST /api/v1/agent-assignments</code>{" "}
            with <code className="font-mono text-xs text-zinc-400">auto_dispatch</code> resolved from
            settings (Phase 67). {agentDomain ? `Domain: ${agentDomain}.` : null}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error ? (
            <div className="rounded-md border border-rose-900/50 bg-rose-950/30 px-3 py-2 text-sm text-rose-200" role="alert">
              {error}
            </div>
          ) : null}
          <div className="space-y-2">
            <Label htmlFor="mc-assign-title">Task title</Label>
            <Input
              id="mc-assign-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Run security scan on /path/to/your/aethos/checkout"
              required
              autoComplete="off"
              maxLength={500}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="mc-assign-description">Description (optional)</Label>
            <Textarea
              id="mc-assign-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What should the agent do?"
              rows={3}
              maxLength={20_000}
            />
          </div>
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium text-zinc-200">Priority</legend>
            <div className="flex gap-4 text-sm">
              {PRIORITY_OPTIONS.map((p) => (
                <label key={p.value} className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="mc-assign-priority"
                    value={p.value}
                    checked={priority === p.value}
                    onChange={(e) => setPriority(e.target.value)}
                    className="h-4 w-4 cursor-pointer accent-violet-500"
                  />
                  <span className="text-zinc-300">{p.label}</span>
                </label>
              ))}
            </div>
          </fieldset>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={submitting || !title.trim()}>
              {submitting ? "Creating…" : "Create & dispatch"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
