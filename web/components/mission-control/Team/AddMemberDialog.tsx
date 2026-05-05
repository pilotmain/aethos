"use client";

import { useState } from "react";
import { UserPlus } from "lucide-react";

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

export type AddMemberDialogProps = {
  onInvite: (userId: string, role: string) => Promise<void>;
  disabled?: boolean;
  disabledReason?: string;
};

export function AddMemberDialog({ onInvite, disabled, disabledReason }: AddMemberDialogProps) {
  const [open, setOpen] = useState(false);
  const [userId, setUserId] = useState("");
  const [role, setRole] = useState("member");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setLoading(true);
    try {
      await onInvite(userId.trim(), role);
      setOpen(false);
      setUserId("");
      setRole("member");
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Invite failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button disabled={disabled} title={disabledReason}>
          <UserPlus className="mr-2 h-4 w-4" />
          Add member
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add organization member</DialogTitle>
          <DialogDescription>
            Calls <span className="font-mono text-zinc-400">POST /api/v1/governance/organizations/&#123;org&#125;/members</span>{" "}
            with a Nexa <strong>user id</strong> (same identifier you use in Login → Connection).
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          {err ? <p className="text-sm text-red-400">{err}</p> : null}
          <div className="space-y-2">
            <Label htmlFor="mc-user-id">User ID</Label>
            <Input
              id="mc-user-id"
              placeholder="telegram:123 or web user id"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              required
              autoComplete="off"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="mc-role">Role</Label>
            <select
              id="mc-role"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="flex h-10 w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
            >
              <option value="admin">admin</option>
              <option value="member">member</option>
              <option value="viewer">viewer</option>
              <option value="auditor">auditor</option>
            </select>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={loading || !userId.trim()}>
              {loading ? "Saving…" : "Add member"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
