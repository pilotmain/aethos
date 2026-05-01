"use client";

import { useCallback, useEffect, useId, useState } from "react";
import { Loader2, X } from "lucide-react";

export type ConfirmDangerDialogProps = {
  open: boolean;
  title: string;
  description: string;
  /** User must type this exact string (trimmed) to enable the action. */
  confirmPhrase: string;
  actionLabel: string;
  onConfirm: () => Promise<void>;
  onCancel: () => void;
  /** variant for button emphasis */
  variant?: "violet" | "redOutline" | "red";
};

export function ConfirmDangerDialog({
  open,
  title,
  description,
  confirmPhrase,
  actionLabel,
  onConfirm,
  onCancel,
  variant = "violet",
}: ConfirmDangerDialogProps) {
  const id = useId();
  const [value, setValue] = useState("");
  const [pending, setPending] = useState(false);
  const [localErr, setLocalErr] = useState<string | null>(null);

  const expected = confirmPhrase.trim();
  const canSubmit = value.trim() === expected && !pending;

  useEffect(() => {
    if (!open) {
      setValue("");
      setLocalErr(null);
      setPending(false);
    }
  }, [open]);

  const handleConfirm = useCallback(async () => {
    if (!canSubmit) return;
    setLocalErr(null);
    setPending(true);
    try {
      await onConfirm();
    } catch (e) {
      setLocalErr((e as Error).message);
    } finally {
      setPending(false);
    }
  }, [canSubmit, onConfirm]);

  if (!open) return null;

  const actionClass =
    variant === "red"
      ? "border border-rose-600/60 bg-rose-600/30 text-rose-50 hover:bg-rose-600/40"
      : variant === "redOutline"
        ? "border border-rose-500/50 bg-transparent text-rose-100 hover:bg-rose-500/10"
        : "border border-violet-500/40 bg-violet-500/20 text-violet-50 hover:bg-violet-500/30";

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby={`${id}-title`}
    >
      <button
        type="button"
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        aria-label="Close"
        onClick={onCancel}
      />
      <div className="relative z-10 w-full max-w-md rounded-xl border border-white/10 bg-zinc-950 p-5 shadow-2xl">
        <div className="mb-3 flex items-start justify-between gap-2">
          <h2 id={`${id}-title`} className="text-base font-semibold text-zinc-100">
            {title}
          </h2>
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md p-1 text-zinc-500 hover:bg-white/5 hover:text-zinc-300"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <p className="mb-4 text-sm text-zinc-400">{description}</p>
        <label className="mb-1 block text-xs font-medium text-zinc-500" htmlFor={`${id}-confirm`}>
          Type <span className="font-mono text-zinc-300">{expected}</span> to continue
        </label>
        <input
          id={`${id}-confirm`}
          type="text"
          autoComplete="off"
          autoFocus
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="mb-3 w-full rounded-lg border border-zinc-700 bg-zinc-900/80 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-violet-500/50 focus:outline-none focus:ring-1 focus:ring-violet-500/30"
          placeholder={expected}
        />
        {localErr ? (
          <p className="mb-3 text-sm text-rose-300" role="alert">
            {localErr}
          </p>
        ) : null}
        <div className="flex flex-wrap justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={pending}
            className="rounded-lg border border-zinc-600 bg-zinc-900 px-3 py-2 text-xs font-medium text-zinc-200 hover:border-zinc-500 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void handleConfirm()}
            disabled={!canSubmit}
            className={`inline-flex items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-40 ${actionClass}`}
          >
            {pending ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> : null}
            {actionLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
