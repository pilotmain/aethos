"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { formatMissionControlApiError } from "@/lib/api";
import {
  type SelfImprovementProposal,
  type SelfImprovementStatus,
  type ValidationSummary,
  applySelfImprovement,
  approveSelfImprovement,
  listSelfImprovementProposals,
  proposeSelfImprovement,
  rejectSelfImprovement,
  revertSelfImprovement,
  runSelfImprovementSandbox,
} from "@/lib/api/self_improvement";

type Flash = { tone: "ok" | "warn" | "err"; text: string } | null;

function statusBadgeClass(status: SelfImprovementStatus): string {
  switch (status) {
    case "pending":
      return "border-zinc-700 bg-zinc-900/60 text-zinc-200";
    case "approved":
      return "border-amber-700 bg-amber-950/40 text-amber-200";
    case "rejected":
      return "border-rose-700 bg-rose-950/40 text-rose-200";
    case "applied":
      return "border-emerald-700 bg-emerald-950/40 text-emerald-200";
    case "reverted":
      return "border-violet-700 bg-violet-950/40 text-violet-200";
    default:
      return "border-zinc-700 bg-zinc-900/60 text-zinc-200";
  }
}

function colorizeDiff(diff: string): JSX.Element[] {
  return diff.split("\n").map((line, i) => {
    let cls = "text-zinc-300";
    if (line.startsWith("+++") || line.startsWith("---") || line.startsWith("diff --git")) {
      cls = "text-zinc-400";
    } else if (line.startsWith("@@")) {
      cls = "text-cyan-300";
    } else if (line.startsWith("+")) {
      cls = "text-emerald-300";
    } else if (line.startsWith("-")) {
      cls = "text-rose-300";
    }
    return (
      <div key={i} className={`whitespace-pre font-mono text-xs ${cls}`}>
        {line || "\u00A0"}
      </div>
    );
  });
}

export default function MissionControlImprovementsPage() {
  const [loading, setLoading] = useState(true);
  const [proposals, setProposals] = useState<SelfImprovementProposal[]>([]);
  const [topError, setTopError] = useState<string | null>(null);
  const [flash, setFlash] = useState<Flash>(null);
  const [busy, setBusy] = useState<{ id: string; kind: string } | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const [title, setTitle] = useState("");
  const [problem, setProblem] = useState("");
  const [targetPathsRaw, setTargetPathsRaw] = useState("");
  const [extraPathsRaw, setExtraPathsRaw] = useState("");
  const [rationale, setRationale] = useState("");
  const [proposing, setProposing] = useState(false);
  const [validation, setValidation] = useState<ValidationSummary | null>(null);
  const [draftDiff, setDraftDiff] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setTopError(null);
    try {
      const r = await listSelfImprovementProposals();
      setProposals(r.proposals);
    } catch (e) {
      const msg = formatMissionControlApiError(
        e instanceof Error ? e.message : String(e),
      );
      // 404 means the feature is disabled — render empty + a hint, not an error.
      if (msg.includes("404") || msg.toLowerCase().includes("disabled")) {
        setProposals([]);
        setTopError(
          "Self-improvement is disabled. Set NEXA_SELF_IMPROVEMENT_ENABLED=true and restart the API to enable.",
        );
      } else {
        setTopError(msg);
        setProposals([]);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const onPropose = useCallback(async () => {
    setProposing(true);
    setFlash(null);
    setValidation(null);
    setDraftDiff(null);
    const targets = targetPathsRaw
      .split(/[\n,]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    const extras = extraPathsRaw
      .split(/[\n,]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (!title.trim() || !problem.trim() || targets.length === 0) {
      setFlash({ tone: "warn", text: "Title, problem statement, and at least one target path are required." });
      setProposing(false);
      return;
    }
    try {
      const r = await proposeSelfImprovement({
        title: title.trim(),
        problem_statement: problem.trim(),
        target_paths: targets,
        extra_context_paths: extras,
        rationale: rationale.trim() || null,
      });
      if (!r.ok) {
        setValidation(r.validation);
        setDraftDiff(r.diff_preview ?? null);
        setFlash({
          tone: "err",
          text: `Validator rejected the LLM diff: ${r.validation.errors.join("; ")}`,
        });
      } else {
        setValidation(r.validation);
        setFlash({
          tone: "ok",
          text: `Proposal created (${r.validation.total_added}+/${r.validation.total_removed}- lines across ${r.validation.files.length} file(s)).`,
        });
        setTitle("");
        setProblem("");
        setTargetPathsRaw("");
        setExtraPathsRaw("");
        setRationale("");
        await load();
      }
    } catch (e) {
      setFlash({
        tone: "err",
        text: `Propose failed: ${formatMissionControlApiError(e instanceof Error ? e.message : String(e))}`,
      });
    } finally {
      setProposing(false);
    }
  }, [title, problem, targetPathsRaw, extraPathsRaw, rationale, load]);

  const runAction = useCallback(
    async (
      id: string,
      kind: "sandbox" | "approve" | "reject" | "apply" | "revert",
    ) => {
      setBusy({ id, kind });
      setFlash(null);
      try {
        if (kind === "sandbox") {
          const r = await runSelfImprovementSandbox(id);
          setFlash({
            tone: r.sandbox.success ? "ok" : "err",
            text: `Sandbox ${r.sandbox.success ? "passed" : "failed"} in ${r.sandbox.duration_s.toFixed(1)}s${r.sandbox.error ? `: ${r.sandbox.error}` : ""}.`,
          });
        } else if (kind === "approve") {
          await approveSelfImprovement(id);
          setFlash({ tone: "ok", text: `Proposal ${id} approved.` });
        } else if (kind === "reject") {
          await rejectSelfImprovement(id);
          setFlash({ tone: "warn", text: `Proposal ${id} rejected.` });
        } else if (kind === "apply") {
          const r = await applySelfImprovement(id);
          setFlash({
            tone: "ok",
            text: `Applied. Local commit ${r.applied_commit_sha?.slice(0, 7) ?? "?"}. ${r.note}`,
          });
        } else if (kind === "revert") {
          const r = await revertSelfImprovement(id);
          setFlash({
            tone: "ok",
            text: `Reverted. New commit ${r.reverted_commit_sha?.slice(0, 7) ?? "?"}.`,
          });
        }
        await load();
      } catch (e) {
        setFlash({
          tone: "err",
          text: `${kind} failed: ${formatMissionControlApiError(e instanceof Error ? e.message : String(e))}`,
        });
      } finally {
        setBusy(null);
      }
    },
    [load],
  );

  const flashClasses = useMemo(() => {
    if (!flash) return "";
    switch (flash.tone) {
      case "err":
        return "border-rose-700 bg-rose-950/40 text-rose-200";
      case "warn":
        return "border-amber-700 bg-amber-950/40 text-amber-200";
      default:
        return "border-emerald-700 bg-emerald-950/40 text-emerald-200";
    }
  }, [flash]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-zinc-50">
          Self-Improvement
        </h1>
        <p className="mt-1 text-sm text-zinc-400">
          Owner-driven proposal pipeline (Phase 73b, safe-adapt v1). Diffs are
          generated by the LLM, validated against an allowlist + size cap, run
          in an isolated <code className="rounded bg-zinc-900 px-1.5 py-0.5 text-xs">git worktree</code> sandbox,
          then applied as a single local <code className="rounded bg-zinc-900 px-1.5 py-0.5 text-xs">[self-improvement]</code> commit on owner approval.
          {" "}<strong>No auto-push, no auto-restart, always revertable.</strong>
        </p>
      </div>

      {topError ? (
        <div className="rounded-lg border border-amber-700 bg-amber-950/40 px-4 py-3 text-sm text-amber-200">
          {topError}
        </div>
      ) : null}

      {flash ? (
        <div
          role="status"
          aria-live="polite"
          className={`flex items-start justify-between gap-3 rounded-lg border px-4 py-3 text-sm ${flashClasses}`}
        >
          <span className="break-words">{flash.text}</span>
          <button
            type="button"
            onClick={() => setFlash(null)}
            className="shrink-0 rounded px-2 py-0.5 text-xs uppercase tracking-wide text-zinc-300 hover:bg-zinc-900/60"
          >
            Dismiss
          </button>
        </div>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Propose an improvement</CardTitle>
          <CardDescription>
            Owner-only. The LLM is given the listed files plus your problem
            statement, and is asked to return a unified diff. Allowed paths
            are restricted by <code className="rounded bg-zinc-900 px-1.5 py-0.5 text-xs">NEXA_SELF_IMPROVEMENT_ALLOWED_PATHS</code>.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3 md:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="si-title">Title</Label>
              <Input
                id="si-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Reduce duplicate sub-agent dispatch in registry"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="si-targets">
                Target paths (comma- or newline-separated)
              </Label>
              <Input
                id="si-targets"
                value={targetPathsRaw}
                onChange={(e) => setTargetPathsRaw(e.target.value)}
                placeholder="app/services/sub_agent_registry.py"
              />
            </div>
          </div>
          <div className="space-y-1">
            <Label htmlFor="si-problem">Problem statement</Label>
            <Textarea
              id="si-problem"
              rows={4}
              value={problem}
              onChange={(e) => setProblem(e.target.value)}
              placeholder="What's broken / inefficient. Be specific about the failure mode."
            />
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="si-extra">Extra context paths (optional)</Label>
              <Input
                id="si-extra"
                value={extraPathsRaw}
                onChange={(e) => setExtraPathsRaw(e.target.value)}
                placeholder="app/services/sub_agent_executor.py"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="si-rationale">Rationale (optional, recorded on commit)</Label>
              <Input
                id="si-rationale"
                value={rationale}
                onChange={(e) => setRationale(e.target.value)}
                placeholder="Closes recurring failure cluster X"
              />
            </div>
          </div>
          <div className="flex items-center justify-between gap-3">
            <div className="text-xs text-zinc-500">
              Targets must fall under the allowlist. The validator enforces
              file-count + line-count caps + a secret-scan over added lines.
            </div>
            <Button
              type="button"
              onClick={() => void onPropose()}
              disabled={proposing}
            >
              {proposing ? "Generating…" : "Generate proposal"}
            </Button>
          </div>
          {validation ? (
            <div className="rounded-md border border-zinc-800 bg-zinc-950/40 p-3 text-xs text-zinc-300">
              <div>
                Files: {validation.files.length} · added {validation.total_added} ·
                removed {validation.total_removed}
              </div>
              {validation.errors.length > 0 ? (
                <ul className="mt-1 list-inside list-disc text-rose-300">
                  {validation.errors.map((e) => (
                    <li key={e}>{e}</li>
                  ))}
                </ul>
              ) : null}
              {validation.warnings.length > 0 ? (
                <ul className="mt-1 list-inside list-disc text-amber-300">
                  {validation.warnings.map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}
          {draftDiff ? (
            <div className="rounded-md border border-zinc-800 bg-zinc-950/60 p-3">
              <div className="mb-2 text-xs uppercase tracking-wide text-zinc-500">
                Rejected diff (preview, first 4 KiB)
              </div>
              <div className="max-h-64 overflow-auto">{colorizeDiff(draftDiff)}</div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Proposals ({proposals.length})</CardTitle>
          <CardDescription>
            Newest first. Sandbox + apply require owner role; apply additionally
            requires a passing sandbox run within the last 60 seconds.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {loading ? (
            <p className="text-sm text-zinc-500">Loading…</p>
          ) : proposals.length === 0 ? (
            <p className="text-sm text-zinc-500">
              No proposals yet. Use the form above to generate one.
            </p>
          ) : (
            proposals.map((p) => {
              const isOpen = !!expanded[p.id];
              const isBusy = busy?.id === p.id;
              return (
                <div
                  key={p.id}
                  className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-3"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-zinc-100">{p.title}</span>
                        <Badge className={statusBadgeClass(p.status)} variant="outline">
                          {p.status}
                        </Badge>
                        {p.sandbox_result ? (
                          <Badge
                            className={
                              p.sandbox_result.success
                                ? "border-emerald-700 bg-emerald-950/40 text-emerald-200"
                                : "border-rose-700 bg-rose-950/40 text-rose-200"
                            }
                            variant="outline"
                          >
                            sandbox: {p.sandbox_result.success ? "pass" : "fail"}
                          </Badge>
                        ) : null}
                      </div>
                      <div className="mt-1 text-xs text-zinc-400">
                        id <code>{p.id}</code> · created {new Date(p.created_at).toLocaleString()}
                        {p.created_by ? ` · by ${p.created_by}` : ""}
                      </div>
                      <div className="mt-1 text-xs text-zinc-500">
                        targets: {p.target_paths.map((t) => (
                          <code key={t} className="mr-1 rounded bg-zinc-900 px-1.5 py-0.5">
                            {t}
                          </code>
                        ))}
                      </div>
                    </div>
                    <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          setExpanded((prev) => ({ ...prev, [p.id]: !prev[p.id] }))
                        }
                      >
                        {isOpen ? "Hide diff" : "View diff"}
                      </Button>
                      {p.status === "pending" || p.status === "approved" ? (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={isBusy}
                          onClick={() => void runAction(p.id, "sandbox")}
                        >
                          {isBusy && busy?.kind === "sandbox" ? "Running…" : "Sandbox"}
                        </Button>
                      ) : null}
                      {p.status === "pending" ? (
                        <>
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={isBusy}
                            onClick={() => void runAction(p.id, "approve")}
                          >
                            Approve
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={isBusy}
                            onClick={() => void runAction(p.id, "reject")}
                          >
                            Reject
                          </Button>
                        </>
                      ) : null}
                      {p.status === "approved" ? (
                        <Button
                          size="sm"
                          disabled={isBusy}
                          onClick={() => void runAction(p.id, "apply")}
                        >
                          {isBusy && busy?.kind === "apply" ? "Applying…" : "Apply"}
                        </Button>
                      ) : null}
                      {p.status === "applied" ? (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={isBusy}
                          onClick={() => void runAction(p.id, "revert")}
                        >
                          {isBusy && busy?.kind === "revert" ? "Reverting…" : "Revert"}
                        </Button>
                      ) : null}
                    </div>
                  </div>
                  {p.applied_commit_sha ? (
                    <div className="mt-2 text-xs text-emerald-300">
                      applied commit: <code>{p.applied_commit_sha.slice(0, 12)}</code>
                    </div>
                  ) : null}
                  {p.reverted_commit_sha ? (
                    <div className="mt-1 text-xs text-violet-300">
                      reverted commit: <code>{p.reverted_commit_sha.slice(0, 12)}</code>
                    </div>
                  ) : null}
                  <div className="mt-2 whitespace-pre-wrap break-words text-sm text-zinc-300">
                    {p.problem_statement}
                  </div>
                  {isOpen ? (
                    <div className="mt-3 rounded-md border border-zinc-800 bg-zinc-950 p-3">
                      <div className="mb-2 text-xs uppercase tracking-wide text-zinc-500">
                        Unified diff
                      </div>
                      <div className="max-h-96 overflow-auto">{colorizeDiff(p.diff)}</div>
                    </div>
                  ) : null}
                  {isOpen && p.sandbox_result ? (
                    <div className="mt-3 rounded-md border border-zinc-800 bg-zinc-950 p-3">
                      <div className="mb-2 text-xs uppercase tracking-wide text-zinc-500">
                        Sandbox steps
                      </div>
                      <ul className="space-y-1 text-xs">
                        {p.sandbox_result.steps.map((s, i) => (
                          <li key={`${p.id}-step-${i}`} className="flex items-start gap-2">
                            <span
                              className={
                                s.exit_code === 0
                                  ? "text-emerald-300"
                                  : "text-rose-300"
                              }
                            >
                              {s.exit_code === 0 ? "✓" : "✗"}
                            </span>
                            <span className="font-mono">
                              {s.name} ({s.duration_s.toFixed(2)}s
                              {s.timed_out ? ", timeout" : ""})
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              );
            })
          )}
        </CardContent>
      </Card>
    </div>
  );
}
