"use client";

import { useState } from "react";

import { createTask } from "@/lib/api/tasks";
import { formatMissionControlApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

interface CreateTaskDialogProps {
  /** Reserved for future board-scoped tasks (API currently lists all `/tasks`). */
  projectId?: string;
  onTaskCreated: () => void | Promise<void>;
}

export function CreateTaskDialog({ onTaskCreated }: CreateTaskDialogProps) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setTitle("");
    setDescription("");
    setError(null);
  };

  const handleCreate = async () => {
    if (!title.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await createTask({
        title: title.trim(),
        description: description.trim() ? description.trim() : null,
      });
      reset();
      setOpen(false);
      await onTaskCreated();
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
        <Button type="button" size="sm">
          New task
        </Button>
      </DialogTrigger>
      <DialogContent className="border-zinc-800 bg-zinc-950">
        <DialogHeader>
          <DialogTitle>New task</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          {error ? <p className="text-sm text-red-400">{error}</p> : null}
          <div className="space-y-2">
            <Label htmlFor="mc-new-task-title">Title</Label>
            <Input
              id="mc-new-task-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Short title"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="mc-new-task-description">Description (optional)</Label>
            <Textarea
              id="mc-new-task-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="button" disabled={submitting || !title.trim()} onClick={() => void handleCreate()}>
              {submitting ? "Creating…" : "Create"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
