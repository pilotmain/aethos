"use client";

/**
 * Phase 75 — Marketplace skill detail modal.
 *
 * Opened from the marketplace page when an operator clicks a remote skill
 * card. Shows the long description, the cross-skill dependency graph, the
 * permissions the skill requests (with a deny-warning when those exceed
 * the operator's allowlist), and links to the README / changelog. The
 * install button is disabled when the skill is already in `installed.yaml`.
 *
 * The modal does NOT fetch the README body itself — we render the URL as
 * a link so the browser handles CSP and out-of-host content. Same goes
 * for the changelog. This keeps the FastAPI side cheap and avoids
 * rendering arbitrary remote markdown inside the dashboard.
 */

import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { formatMissionControlApiError } from "@/lib/api";
import {
  type MarketplaceCapabilities,
  type MarketplaceSkillInfo,
  type SkillDetails,
  getSkillDetails,
} from "@/lib/api/marketplace";

type Props = {
  open: boolean;
  skill: MarketplaceSkillInfo | null;
  capabilities: MarketplaceCapabilities | null;
  isInstalled: boolean;
  onOpenChange: (open: boolean) => void;
  onInstall: (name: string) => void;
  installBusy?: boolean;
};

export function SkillDetailModal({
  open,
  skill,
  capabilities,
  isInstalled,
  onOpenChange,
  onInstall,
  installBusy = false,
}: Props) {
  const [details, setDetails] = useState<SkillDetails | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !skill) {
      setDetails(null);
      setError(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const fetched = await getSkillDetails(skill.name);
        if (!cancelled) setDetails(fetched);
      } catch (e) {
        if (!cancelled) {
          setError(
            formatMissionControlApiError(e instanceof Error ? e.message : String(e)),
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, skill]);

  const merged: MarketplaceSkillInfo | null =
    (details?.skill ?? skill) as MarketplaceSkillInfo | null;
  const dependencies = details?.dependencies ?? skill?.skill_dependencies ?? [];
  const permissions = details?.permissions ?? skill?.permissions ?? [];

  // Permission allowlist warning — match the same rule the executor enforces.
  const sandboxOn = capabilities?.sandbox_mode ?? true;
  const allowSet = new Set((capabilities?.permissions_allowlist ?? []).map((p) => p.toLowerCase()));
  const blockedPerms = sandboxOn
    ? permissions.filter((p) => !allowSet.has(p.toLowerCase()))
    : [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2">
            <span>{skill?.name ?? "Loading…"}</span>
            {skill?.version ? (
              <span className="text-xs font-normal text-zinc-500">v{skill.version}</span>
            ) : null}
            {isInstalled ? <Badge variant="success">installed</Badge> : null}
            {skill?.signature ? <Badge variant="outline">signed</Badge> : null}
          </DialogTitle>
          <DialogDescription className="text-xs text-zinc-400">
            {merged?.publisher ? `publisher: ${merged.publisher}` : null}
            {merged?.author && merged.author !== "unknown" ? ` · author: ${merged.author}` : ""}
            {merged?.category ? ` · category: ${merged.category}` : ""}
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="py-6 text-center text-sm text-zinc-500">Loading details…</div>
        ) : error ? (
          <div className="rounded border border-red-900/50 bg-red-950/40 px-3 py-2 text-sm text-red-200">
            {error}
          </div>
        ) : null}

        <div className="space-y-4 text-sm text-zinc-200">
          {merged?.description ? (
            <p className="whitespace-pre-wrap leading-relaxed text-zinc-300">
              {merged.description}
            </p>
          ) : (
            <p className="text-zinc-500">No description provided.</p>
          )}

          {merged?.tags?.length ? (
            <div className="space-y-1">
              <div className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
                Tags
              </div>
              <div className="flex flex-wrap gap-1.5">
                {merged.tags.slice(0, 24).map((tag) => (
                  <Badge key={tag} variant="secondary">
                    {tag}
                  </Badge>
                ))}
              </div>
            </div>
          ) : null}

          {dependencies.length > 0 ? (
            <div className="space-y-1">
              <div className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
                Depends on (other skills)
              </div>
              <div className="flex flex-wrap gap-1.5">
                {dependencies.map((d) => (
                  <Badge key={d} variant="outline" className="font-mono">
                    {d}
                  </Badge>
                ))}
              </div>
              <p className="text-xs text-zinc-500">
                These will be installed automatically before {merged?.name ?? "this skill"}.
              </p>
            </div>
          ) : null}

          {permissions.length > 0 ? (
            <div className="space-y-1">
              <div className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
                Requested permissions
              </div>
              <div className="flex flex-wrap gap-1.5">
                {permissions.map((p) => {
                  const blocked = blockedPerms.includes(p);
                  return (
                    <Badge
                      key={p}
                      variant={blocked ? "warning" : "secondary"}
                      className="font-mono"
                    >
                      {p}
                      {blocked ? " (denied)" : ""}
                    </Badge>
                  );
                })}
              </div>
              {blockedPerms.length > 0 ? (
                <p className="text-xs text-amber-300">
                  Sandbox mode will block this skill at runtime — its permissions exceed the
                  operator allowlist (
                  <code className="font-mono text-[11px]">
                    NEXA_MARKETPLACE_SKILL_PERMISSIONS_ALLOWLIST
                  </code>
                  ). Install is still possible; execution will fail until the allowlist is
                  widened.
                </p>
              ) : null}
            </div>
          ) : null}

          <div className="flex flex-wrap gap-3 text-xs">
            {details?.documentation?.readme_url ? (
              <a
                className="underline hover:text-zinc-100"
                href={details.documentation.readme_url}
                rel="noreferrer noopener"
                target="_blank"
              >
                README ↗
              </a>
            ) : null}
            {details?.documentation?.changelog_url ? (
              <a
                className="underline hover:text-zinc-100"
                href={details.documentation.changelog_url}
                rel="noreferrer noopener"
                target="_blank"
              >
                Changelog ↗
              </a>
            ) : null}
            {details?.documentation?.manifest_url ? (
              <a
                className="underline hover:text-zinc-100"
                href={details.documentation.manifest_url}
                rel="noreferrer noopener"
                target="_blank"
              >
                Manifest ↗
              </a>
            ) : null}
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-end gap-2 pt-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
          {skill ? (
            <Button
              onClick={() => onInstall(skill.name)}
              disabled={installBusy || isInstalled}
            >
              {installBusy
                ? "Installing…"
                : isInstalled
                  ? "Already installed"
                  : "Install"}
            </Button>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default SkillDetailModal;
