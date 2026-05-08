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
  type SelfImprovementCapabilities,
  type SelfImprovementProposal,
  type SelfImprovementStatus,
  type SystemHealthDetailed,
  type ValidationSummary,
  applySelfImprovement,
  approveSelfImprovement,
  getSelfImprovementPrStatus,
  getSystemHealthDetailed,
  listSelfImprovementProposals,
  mergeSelfImprovementPr,
  openSelfImprovementPr,
  proposeSelfImprovement,
  refreshSelfImprovementCi,
  rejectSelfImprovement,
  restartSelfImprovement,
  revertScanNowSelfImprovement,
  revertSelfImprovement,
  revertSelfImprovementMerge,
  runSelfImprovementSandbox,
  selfImprovementCapabilities,
  setSelfImprovementAutoMerge,
  setSelfImprovementAutoRevert,
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
    case "merged":
      return "border-emerald-700 bg-emerald-950/40 text-emerald-200";
    case "reverted":
      return "border-violet-700 bg-violet-950/40 text-violet-200";
    case "pr_open":
      return "border-cyan-700 bg-cyan-950/40 text-cyan-200";
    case "revert_pr_open":
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
  const [caps, setCaps] = useState<SelfImprovementCapabilities | null>(null);
  const [health, setHealth] = useState<SystemHealthDetailed | null>(null);

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

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const c = await selfImprovementCapabilities();
        if (!cancelled) setCaps(c);
      } catch {
        if (!cancelled) setCaps(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Phase 73e — poll the detailed health endpoint so the capabilities
  // banner can show the rolling error rate + auto-revert cooldown state.
  // Refreshed alongside proposals so a manual reload picks up the
  // newest snapshot.
  const refreshHealth = useCallback(async () => {
    try {
      const h = await getSystemHealthDetailed();
      setHealth(h);
    } catch {
      setHealth(null);
    }
  }, []);

  useEffect(() => {
    void refreshHealth();
    const t = window.setInterval(() => {
      void refreshHealth();
    }, 30_000);
    return () => window.clearInterval(t);
  }, [refreshHealth]);

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
      kind:
        | "sandbox"
        | "approve"
        | "reject"
        | "apply"
        | "revert"
        | "open-pr"
        | "pr-status"
        | "merge-pr"
        | "revert-merge"
        | "refresh-ci"
        | "auto-merge-on"
        | "auto-merge-off"
        | "auto-revert-disable"
        | "auto-revert-enable"
        | "revert-scan-now"
        | "restart",
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
        } else if (kind === "open-pr") {
          const r = await openSelfImprovementPr(id);
          setFlash({
            tone: "ok",
            text: `PR #${r.pr.number} opened on ${r.pr.head_branch} → ${r.pr.base_branch}.`,
          });
        } else if (kind === "pr-status") {
          const r = await getSelfImprovementPrStatus(id);
          const m = r.pr.mergeable;
          const tone: "ok" | "warn" | "err" =
            r.pr.merged ? "ok" : m === true ? "ok" : m === false ? "err" : "warn";
          setFlash({
            tone,
            text:
              `PR #${r.pr.number} state=${r.pr.state}, merged=${r.pr.merged}, ` +
              `mergeable=${m === null ? "computing…" : String(m)}` +
              `${r.pr.mergeable_state ? ` (${r.pr.mergeable_state})` : ""}.`,
          });
        } else if (kind === "merge-pr") {
          const r = await mergeSelfImprovementPr(id);
          setFlash({
            tone: "ok",
            text: `PR merged. Remote commit ${r.merge_commit_sha?.slice(0, 7) ?? "?"}. ${r.note ?? ""}`,
          });
        } else if (kind === "revert-merge") {
          const r = await revertSelfImprovementMerge(id);
          setFlash({
            tone: "ok",
            text: `Revert PR #${r.revert_pr.number} opened on ${r.revert_pr.head_branch}.`,
          });
        } else if (kind === "refresh-ci") {
          const r = await refreshSelfImprovementCi(id);
          const tone: "ok" | "warn" | "err" =
            r.ci.state === "success"
              ? "ok"
              : r.ci.state === "failure" || r.ci.state === "error"
                ? "err"
                : "warn";
          setFlash({
            tone,
            text:
              `CI for PR head ${r.ci.head_sha.slice(0, 7)}: ` +
              `state=${r.ci.state} (${r.ci.total_count} check${r.ci.total_count === 1 ? "" : "s"}).`,
          });
        } else if (kind === "auto-merge-on" || kind === "auto-merge-off") {
          const enabled = kind === "auto-merge-on";
          const r = await setSelfImprovementAutoMerge(id, enabled);
          setFlash({
            tone: "ok",
            text: `Auto-merge on CI pass: ${r.auto_merge_on_ci_pass ? "ENABLED" : "disabled"} for ${id}.`,
          });
        } else if (kind === "restart") {
          const r = await restartSelfImprovement();
          setFlash({
            tone: r.status === "scheduled" ? "ok" : "warn",
            text: `Restart ${r.status} (method=${r.method}${r.delay_s ? `, delay=${r.delay_s}s` : ""}).`,
          });
        } else if (kind === "auto-revert-disable" || kind === "auto-revert-enable") {
          const disable = kind === "auto-revert-disable";
          const r = await setSelfImprovementAutoRevert(id, disable);
          setFlash({
            tone: "ok",
            text: `Auto-revert: ${r.auto_revert_disabled ? "DISABLED" : "enabled (watching)"} for ${id}.`,
          });
        } else if (kind === "revert-scan-now") {
          const r = await revertScanNowSelfImprovement();
          if (r.status === "disabled") {
            setFlash({
              tone: "warn",
              text:
                "Auto-revert is globally disabled. Set NEXA_SELF_IMPROVEMENT_AUTO_REVERT_ENABLED=true to arm.",
            });
          } else {
            const c = r.counters;
            setFlash({
              tone: c && c.reverted > 0 ? "warn" : "ok",
              text:
                `Revert scan: scanned=${c?.scanned ?? 0}, watched=${c?.watched ?? 0}, ` +
                `cleared=${c?.cleared ?? 0}, reverted=${c?.reverted ?? 0}` +
                `${c && c.revert_errors > 0 ? `, revert_errors=${c.revert_errors}` : ""}.`,
            });
          }
          await refreshHealth();
        }
        await load();
        await refreshHealth();
      } catch (e) {
        setFlash({
          tone: "err",
          text: `${kind} failed: ${formatMissionControlApiError(e instanceof Error ? e.message : String(e))}`,
        });
      } finally {
        setBusy(null);
      }
    },
    [load, refreshHealth],
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

      {caps ? (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-xs text-zinc-400">
          <span>
            <strong className="text-zinc-200">GitHub auto-merge:</strong>{" "}
            {caps.github.enabled
              ? caps.github.configured
                ? `enabled (${caps.github.owner}/${caps.github.repo} · ${caps.github.merge_method} · base ${caps.github.base_branch})`
                : "enabled but not fully configured (set NEXA_SELF_IMPROVEMENT_GITHUB_TOKEN/OWNER/REPO)"
              : "disabled (set NEXA_SELF_IMPROVEMENT_GITHUB_ENABLED=true to opt in)"}
          </span>
          <span className="text-zinc-500">·</span>
          <span>
            <strong className="text-zinc-200">Wait for CI:</strong>{" "}
            {caps.ci.wait_for_ci
              ? `on (poll ${caps.ci.poll_interval_seconds}s, max age ${Math.round(caps.ci.max_age_seconds / 60)}m)`
              : "off"}
          </span>
          <span className="text-zinc-500">·</span>
          <span>
            <strong className="text-zinc-200">Auto-restart:</strong>{" "}
            {caps.auto_restart.enabled
              ? `enabled (${caps.auto_restart.method})`
              : `disabled (method=${caps.auto_restart.method})`}
          </span>
          {caps.auto_restart.enabled ? (
            <Button
              size="sm"
              variant="outline"
              onClick={() => void runAction("__global__", "restart")}
            >
              Restart API now
            </Button>
          ) : null}
          <span className="text-zinc-500">·</span>
          <span>
            <strong className="text-zinc-200">Auto-revert:</strong>{" "}
            {caps.auto_revert.enabled ? (
              <>
                on (≥{caps.auto_revert.min_sample_size} mistakes,{" "}
                {Math.round(caps.auto_revert.threshold * 100)}% threshold,{" "}
                {Math.round(caps.auto_revert.observation_window_seconds / 60)}m
                window)
                {caps.auto_revert.in_cooldown ? (
                  <span className="ml-1 rounded border border-amber-700 bg-amber-950/40 px-1.5 py-0.5 text-amber-200">
                    cooldown active — auto-merge paused
                  </span>
                ) : null}
              </>
            ) : (
              "disabled (set NEXA_SELF_IMPROVEMENT_AUTO_REVERT_ENABLED=true)"
            )}
          </span>
          {caps.auto_revert.enabled ? (
            <Button
              size="sm"
              variant="outline"
              onClick={() => void runAction("__global__", "revert-scan-now")}
            >
              Scan now
            </Button>
          ) : null}
          {health ? (
            <>
              <span className="text-zinc-500">·</span>
              <span>
                <strong className="text-zinc-200">Health:</strong>{" "}
                {health.errors.errors}/{health.errors.total_actions} errors over
                last {Math.round(health.errors.window_seconds / 60)}m
                {" "}({(health.errors.error_rate * 100).toFixed(1)}%)
                {health.heartbeat.enabled ? (
                  <>
                    {" · heartbeat "}
                    {health.heartbeat.age_seconds == null
                      ? "unknown"
                      : `${Math.round(health.heartbeat.age_seconds)}s ago`}
                    {health.heartbeat.stale ? (
                      <span className="ml-1 rounded border border-rose-700 bg-rose-950/40 px-1.5 py-0.5 text-rose-200">
                        stale
                      </span>
                    ) : null}
                  </>
                ) : null}
              </span>
            </>
          ) : null}
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
                      {/* Phase 73c — GitHub flow buttons. Gated by capabilities so the
                          UI hides them entirely when the GitHub flow is off. */}
                      {caps?.github.enabled && p.status === "approved" ? (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={isBusy}
                          onClick={() => void runAction(p.id, "open-pr")}
                        >
                          {isBusy && busy?.kind === "open-pr" ? "Opening PR…" : "Open PR"}
                        </Button>
                      ) : null}
                      {caps?.github.enabled && p.status === "pr_open" ? (
                        <>
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={isBusy}
                            onClick={() => void runAction(p.id, "pr-status")}
                          >
                            {isBusy && busy?.kind === "pr-status"
                              ? "Refreshing…"
                              : "Refresh PR status"}
                          </Button>
                          <Button
                            size="sm"
                            disabled={isBusy}
                            onClick={() => void runAction(p.id, "merge-pr")}
                          >
                            {isBusy && busy?.kind === "merge-pr"
                              ? "Merging…"
                              : "Merge if mergeable"}
                          </Button>
                        </>
                      ) : null}
                      {caps?.github.enabled && p.status === "merged" ? (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={isBusy}
                          onClick={() => void runAction(p.id, "revert-merge")}
                        >
                          {isBusy && busy?.kind === "revert-merge"
                            ? "Opening revert PR…"
                            : "Revert via PR"}
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
                  {p.pr_number ? (
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
                      <span className="text-cyan-300">
                        PR{" "}
                        {p.pr_url ? (
                          <a
                            href={p.pr_url}
                            target="_blank"
                            rel="noreferrer"
                            className="underline"
                          >
                            #{p.pr_number}
                          </a>
                        ) : (
                          <code>#{p.pr_number}</code>
                        )}
                        {p.github_branch ? (
                          <>
                            {" "}on branch <code>{p.github_branch}</code>
                          </>
                        ) : null}
                      </span>
                      {/* Phase 73d — CI badge. Only render once we have a polled state. */}
                      {p.ci_state ? (
                        <span
                          className={`inline-flex items-center rounded-md border px-1.5 py-0.5 ${
                            p.ci_state === "success"
                              ? "border-emerald-700 bg-emerald-950/40 text-emerald-200"
                              : p.ci_state === "failure" || p.ci_state === "error"
                                ? "border-rose-700 bg-rose-950/40 text-rose-200"
                                : p.ci_state === "timed_out"
                                  ? "border-amber-700 bg-amber-950/40 text-amber-200"
                                  : p.ci_state === "passed_awaiting_sandbox"
                                    ? "border-amber-700 bg-amber-950/40 text-amber-200"
                                    : "border-zinc-700 bg-zinc-900/60 text-zinc-200"
                          }`}
                          title={p.ci_checked_at ? `last checked ${p.ci_checked_at}` : undefined}
                        >
                          CI: {p.ci_state}
                        </span>
                      ) : null}
                      {/* Phase 73d — auto-merge-on-CI toggle (only meaningful for pr_open + GitHub enabled). */}
                      {caps?.github.enabled && p.status === "pr_open" ? (
                        <>
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={isBusy}
                            onClick={() => void runAction(p.id, "refresh-ci")}
                          >
                            {isBusy && busy?.kind === "refresh-ci" ? "Polling…" : "Refresh CI"}
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={isBusy}
                            onClick={() =>
                              void runAction(
                                p.id,
                                p.auto_merge_on_ci_pass ? "auto-merge-off" : "auto-merge-on",
                              )
                            }
                            title={
                              p.auto_merge_on_ci_pass
                                ? "Stop auto-merging this proposal when CI passes."
                                : "Auto-merge this PR when CI goes green and the local sandbox is still fresh."
                            }
                          >
                            {p.auto_merge_on_ci_pass
                              ? "Disable auto-merge"
                              : "Auto-merge on CI pass"}
                          </Button>
                        </>
                      ) : null}
                    </div>
                  ) : null}
                  {/* Phase 73d — stale-sandbox banner: CI saw green but the
                      monitor couldn't auto-merge because the local sandbox
                      went stale (>60s old). Operator needs to re-run sandbox. */}
                  {p.ci_state === "passed_awaiting_sandbox" ? (
                    <div className="mt-2 rounded-md border border-amber-700 bg-amber-950/30 px-3 py-2 text-xs text-amber-200">
                      CI passed on GitHub, but the local sandbox is older than
                      60s so auto-merge is paused. Re-run <strong>Sandbox</strong>{" "}
                      and then click <strong>Merge if mergeable</strong>.
                    </div>
                  ) : null}
                  {p.merge_commit_sha ? (
                    <div className="mt-1 text-xs text-emerald-300">
                      merged commit: <code>{p.merge_commit_sha.slice(0, 12)}</code>
                    </div>
                  ) : null}
                  {/* Phase 73e — auto-revert badge + per-proposal disable
                      toggle. Only meaningful for proposals that reached the
                      ``merged`` state (i.e. have a ``merged_at``). */}
                  {p.merged_at ? (
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
                      <span
                        className={`inline-flex items-center rounded-md border px-1.5 py-0.5 ${
                          p.auto_revert_state === "reverted"
                            ? "border-rose-700 bg-rose-950/40 text-rose-200"
                            : p.auto_revert_state === "cleared"
                              ? "border-emerald-700 bg-emerald-950/40 text-emerald-200"
                              : p.auto_revert_state === "disabled" || p.auto_revert_disabled
                                ? "border-zinc-700 bg-zinc-900/60 text-zinc-300"
                                : "border-amber-700 bg-amber-950/40 text-amber-200"
                        }`}
                        title={
                          p.auto_revert_decided_at
                            ? `last decided ${p.auto_revert_decided_at}`
                            : undefined
                        }
                      >
                        Auto-revert: {p.auto_revert_state ?? (p.auto_revert_disabled ? "disabled" : "watching")}
                      </span>
                      {caps?.auto_revert.enabled && p.status === "merged" ? (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={isBusy}
                          onClick={() =>
                            void runAction(
                              p.id,
                              p.auto_revert_disabled
                                ? "auto-revert-enable"
                                : "auto-revert-disable",
                            )
                          }
                          title={
                            p.auto_revert_disabled
                              ? "Re-arm the watcher for this proposal."
                              : "Stop the watcher from auto-opening a revert PR for this proposal."
                          }
                        >
                          {p.auto_revert_disabled
                            ? "Re-arm auto-revert"
                            : "Disable auto-revert"}
                        </Button>
                      ) : null}
                    </div>
                  ) : null}
                  {p.revert_pr_number ? (
                    <div className="mt-1 text-xs text-violet-300">
                      revert PR{" "}
                      {p.revert_pr_url ? (
                        <a
                          href={p.revert_pr_url}
                          target="_blank"
                          rel="noreferrer"
                          className="underline"
                        >
                          #{p.revert_pr_number}
                        </a>
                      ) : (
                        <code>#{p.revert_pr_number}</code>
                      )}
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
