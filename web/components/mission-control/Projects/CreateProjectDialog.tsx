"use client";

import { useState } from "react";

import { createWorkspaceProject } from "@/lib/api/projects";
import { formatMissionControlApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

interface CreateProjectDialogProps {
  onCreated: () => void | Promise<void>;
}

export function CreateProjectDialog({ onCreated }: CreateProjectDialogProps) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [path, setPath] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setName("");
    setPath("");
    setDescription("");
    setError(null);
  };

  const handleCreate = async () => {
    if (!name.trim() || !path.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await createWorkspaceProject({
        name: name.trim(),
        path: path.trim(),
        description: description.trim() ? description.trim() : null,
      });
      reset();
      setOpen(false);
      await onCreated();
    } catch (e) {
      setError(formatMissionControlApiError(e instanceof Error ? e.message : String(e)));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) reset();
      }}
    >
      <DialogTrigger asChild>
        <Button type="button" variant="outline" size="sm">
          New workspace project
        </Button>
      </DialogTrigger>
      <DialogContent className="border-zinc-800 bg-zinc-950">
        <DialogHeader>
          <DialogTitle>New workspace project</DialogTitle>
        </DialogHeader>
        <p className="text-xs text-zinc-500">
          Creates an AethOS workspace folder mapping via POST /api/v1/web/workspace/nexa-projects (path + name required).
        </p>
        <div className="space-y-4">
          {error ? <p className="text-sm text-red-400">{error}</p> : null}
          <div className="space-y-2">
            <Label htmlFor="mc-ws-name">Name</Label>
            <Input id="mc-ws-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="My repo" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="mc-ws-path">Path</Label>
            <Input
              id="mc-ws-path"
              value={path}
              onChange={(e) => setPath(e.target.value)}
              placeholder="~/projects/my-app"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="mc-ws-description">Description (optional)</Label>
            <Textarea
              id="mc-ws-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="button" disabled={submitting || !name.trim() || !path.trim()} onClick={() => void handleCreate()}>
              {submitting ? "Creating…" : "Create"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
