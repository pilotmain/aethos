"use client";

import { useEffect, useState } from "react";

import type { Task } from "@/types/mission-control";
import { patchTask } from "@/lib/api/tasks";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

import { formatMissionControlApiError } from "@/lib/api";

interface TaskDetailDialogProps {
  open: boolean;
  task: Task | null;
  readOnly?: boolean;
  onClose: () => void;
  onAfterSave: () => void | Promise<void>;
}

export function TaskDetailDialog({ open, task, readOnly, onClose, onAfterSave }: TaskDetailDialogProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState<Task["status"]>("pending");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !task) return;
    setTitle(task.title);
    setDescription(task.description ?? "");
    setStatus(task.status);
    setError(null);
  }, [open, task]);

  const handleSave = async () => {
    if (!task || readOnly) return;
    setSaving(true);
    setError(null);
    try {
      await patchTask(task.id, {
        title,
        description: description.trim() ? description : null,
        status,
      });
      await onAfterSave();
    } catch (e) {
      setError(formatMissionControlApiError(e instanceof Error ? e.message : String(e)));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
    >
      <DialogContent className="max-w-md border-zinc-800 bg-zinc-950">
        <DialogHeader>
          <DialogTitle>{readOnly ? "Task details (read-only)" : "Task details"}</DialogTitle>
        </DialogHeader>
        {task ? (
          <div className="space-y-4">
            {error ? <p className="text-sm text-red-400">{error}</p> : null}
            <div className="space-y-2">
              <Label htmlFor="mc-task-title">Title</Label>
              <Input
                id="mc-task-title"
                value={title}
                disabled={readOnly}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="mc-task-description">Description</Label>
              <Textarea
                id="mc-task-description"
                value={description}
                disabled={readOnly}
                onChange={(e) => setDescription(e.target.value)}
                rows={4}
              />
            </div>
            <div className="space-y-2">
              <Label>Status</Label>
              <Select value={status} disabled={readOnly} onValueChange={(v) => setStatus(v as Task["status"])}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="pending">To Do</SelectItem>
                  <SelectItem value="in_progress">In Progress</SelectItem>
                  <SelectItem value="done">Done</SelectItem>
                  <SelectItem value="blocked">Blocked</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" type="button" onClick={onClose}>
                {readOnly ? "Close" : "Cancel"}
              </Button>
              {readOnly ? null : (
                <Button type="button" disabled={saving || !title.trim()} onClick={() => void handleSave()}>
                  {saving ? "Saving…" : "Save changes"}
                </Button>
              )}
            </div>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
