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
import { formatMissionControlApiError } from "@/lib/api";
import {
  type InstalledSkillRow,
  type MarketplaceSkillInfo,
  installSkill,
  listInstalledSkills,
  popularSkills,
  searchSkills,
  uninstallSkill,
  updateSkill,
} from "@/lib/api/marketplace";

type RowState = {
  busy: boolean;
  error: string | null;
};

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    return d.toLocaleString();
  } catch {
    return value;
  }
}

function shortDescription(value: string | null | undefined, max = 160): string {
  const s = (value || "").trim();
  if (s.length <= max) return s;
  return `${s.slice(0, max - 1)}…`;
}

export default function MissionControlMarketplacePage() {
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<MarketplaceSkillInfo[]>([]);
  const [popular, setPopular] = useState<MarketplaceSkillInfo[]>([]);
  const [installed, setInstalled] = useState<InstalledSkillRow[]>([]);
  const [topError, setTopError] = useState<string | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [installedError, setInstalledError] = useState<string | null>(null);
  const [loadingInstalled, setLoadingInstalled] = useState(true);
  const [loadingPopular, setLoadingPopular] = useState(true);
  const [installState, setInstallState] = useState<Record<string, RowState>>({});
  const [installedState, setInstalledState] = useState<Record<string, RowState>>({});

  const reloadInstalled = useCallback(async () => {
    setLoadingInstalled(true);
    setInstalledError(null);
    try {
      const rows = await listInstalledSkills();
      setInstalled(rows);
    } catch (e) {
      setInstalled([]);
      setInstalledError(
        formatMissionControlApiError(e instanceof Error ? e.message : String(e)),
      );
    } finally {
      setLoadingInstalled(false);
    }
  }, []);

  const reloadPopular = useCallback(async () => {
    setLoadingPopular(true);
    setTopError(null);
    try {
      const rows = await popularSkills(20);
      setPopular(rows);
    } catch (e) {
      setPopular([]);
      setTopError(formatMissionControlApiError(e instanceof Error ? e.message : String(e)));
    } finally {
      setLoadingPopular(false);
    }
  }, []);

  useEffect(() => {
    void reloadInstalled();
    void reloadPopular();
  }, [reloadInstalled, reloadPopular]);

  const installedNames = useMemo(
    () => new Set(installed.map((s) => s.name.toLowerCase())),
    [installed],
  );

  const handleSearch = useCallback(
    async (e?: React.FormEvent) => {
      if (e) e.preventDefault();
      const q = query.trim();
      if (!q) {
        setSearchResults([]);
        setSearchError(null);
        return;
      }
      setSearching(true);
      setSearchError(null);
      try {
        const rows = await searchSkills(q, 25);
        setSearchResults(rows);
      } catch (err) {
        setSearchResults([]);
        setSearchError(
          formatMissionControlApiError(err instanceof Error ? err.message : String(err)),
        );
      } finally {
        setSearching(false);
      }
    },
    [query],
  );

  const setBusyRemote = (name: string, busy: boolean, errMsg: string | null = null) => {
    setInstallState((prev) => ({ ...prev, [name]: { busy, error: errMsg } }));
  };

  const setBusyInstalled = (name: string, busy: boolean, errMsg: string | null = null) => {
    setInstalledState((prev) => ({ ...prev, [name]: { busy, error: errMsg } }));
  };

  const handleInstall = useCallback(
    async (name: string) => {
      setBusyRemote(name, true);
      try {
        await installSkill(name, "latest", false);
        await reloadInstalled();
        setBusyRemote(name, false);
      } catch (err) {
        setBusyRemote(
          name,
          false,
          formatMissionControlApiError(err instanceof Error ? err.message : String(err)),
        );
      }
    },
    [reloadInstalled],
  );

  const handleUninstall = useCallback(
    async (name: string) => {
      setBusyInstalled(name, true);
      try {
        await uninstallSkill(name);
        await reloadInstalled();
        setBusyInstalled(name, false);
      } catch (err) {
        setBusyInstalled(
          name,
          false,
          formatMissionControlApiError(err instanceof Error ? err.message : String(err)),
        );
      }
    },
    [reloadInstalled],
  );

  const handleUpdate = useCallback(
    async (name: string) => {
      setBusyInstalled(name, true);
      try {
        await updateSkill(name, false);
        await reloadInstalled();
        setBusyInstalled(name, false);
      } catch (err) {
        setBusyInstalled(
          name,
          false,
          formatMissionControlApiError(err instanceof Error ? err.message : String(err)),
        );
      }
    },
    [reloadInstalled],
  );

  function renderRemoteCard(skill: MarketplaceSkillInfo) {
    const isInstalled = installedNames.has(skill.name.toLowerCase());
    const state = installState[skill.name] || { busy: false, error: null };
    return (
      <Card key={`remote-${skill.name}`}>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-1">
              <CardTitle className="text-base">
                {skill.name}{" "}
                <span className="text-xs font-normal text-zinc-500">v{skill.version}</span>
              </CardTitle>
              <CardDescription className="flex flex-wrap items-center gap-2 text-xs">
                <span>publisher: {skill.publisher || "community"}</span>
                {skill.author ? (
                  <>
                    <span>•</span>
                    <span>author: {skill.author}</span>
                  </>
                ) : null}
                {skill.downloads ? (
                  <>
                    <span>•</span>
                    <span>{skill.downloads.toLocaleString()} downloads</span>
                  </>
                ) : null}
                {skill.rating ? (
                  <>
                    <span>•</span>
                    <span>★ {skill.rating.toFixed(1)}</span>
                  </>
                ) : null}
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              {isInstalled ? <Badge variant="success">installed</Badge> : null}
              {skill.signature ? <Badge variant="outline">signed</Badge> : null}
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {skill.description ? (
            <p className="text-sm text-zinc-300">{shortDescription(skill.description)}</p>
          ) : null}

          {skill.tags?.length ? (
            <div className="flex flex-wrap gap-1.5">
              {skill.tags.slice(0, 8).map((tag) => (
                <Badge key={tag} variant="secondary">
                  {tag}
                </Badge>
              ))}
            </div>
          ) : null}

          {state.error ? (
            <div className="rounded border border-red-900/50 bg-red-950/40 px-3 py-2 text-xs text-red-200">
              {state.error}
            </div>
          ) : null}

          <div className="flex flex-wrap items-center gap-2 pt-1">
            <Button
              size="sm"
              onClick={() => void handleInstall(skill.name)}
              disabled={state.busy || isInstalled}
            >
              {state.busy ? "Installing…" : isInstalled ? "Already installed" : "Install"}
            </Button>
            <span className="text-xs text-zinc-500">
              updated {formatDate(skill.updated_at)}
            </span>
          </div>
        </CardContent>
      </Card>
    );
  }

  function renderInstalledCard(skill: InstalledSkillRow) {
    const state = installedState[skill.name] || { busy: false, error: null };
    return (
      <Card key={`installed-${skill.name}`}>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-1">
              <CardTitle className="text-base">
                {skill.name}{" "}
                <span className="text-xs font-normal text-zinc-500">v{skill.version}</span>
              </CardTitle>
              <CardDescription className="flex flex-wrap items-center gap-2 text-xs">
                <span>source: {skill.source}</span>
                {skill.publisher ? (
                  <>
                    <span>•</span>
                    <span>publisher: {skill.publisher}</span>
                  </>
                ) : null}
                <span>•</span>
                <span>installed {formatDate(skill.installed_at)}</span>
              </CardDescription>
            </div>
            <Badge variant={skill.status === "installed" ? "success" : "warning"}>
              {skill.status}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {state.error ? (
            <div className="rounded border border-red-900/50 bg-red-950/40 px-3 py-2 text-xs text-red-200">
              {state.error}
            </div>
          ) : null}
          <div className="flex flex-wrap items-center gap-2">
            {skill.source === "clawhub" ? (
              <Button
                size="sm"
                variant="outline"
                onClick={() => void handleUpdate(skill.name)}
                disabled={state.busy}
              >
                {state.busy ? "Working…" : "Check for update"}
              </Button>
            ) : null}
            <Button
              size="sm"
              variant="destructive"
              onClick={() => void handleUninstall(skill.name)}
              disabled={state.busy}
            >
              Uninstall
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-zinc-50">Skill marketplace</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Discover community plugin skills from a ClawHub-compatible registry. Install / uninstall
          / update require the Telegram-linked owner; everything else (search, popular, installed
          list) is read-only for any signed-in user.
        </p>
      </div>

      <form
        onSubmit={(e) => void handleSearch(e)}
        className="flex flex-wrap items-center gap-2"
      >
        <Input
          placeholder="Search skills (e.g. 'github', 'web scraper', 'pdf')"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="flex-1 min-w-[260px]"
        />
        <Button type="submit" disabled={searching}>
          {searching ? "Searching…" : "Search"}
        </Button>
      </form>

      {searchError ? (
        <div className="rounded-lg border border-red-900/50 bg-red-950/40 px-4 py-3 text-sm text-red-200">
          {searchError}
        </div>
      ) : null}

      {searchResults.length > 0 ? (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
            Search results
          </h2>
          <div className="grid gap-3">{searchResults.map(renderRemoteCard)}</div>
        </section>
      ) : null}

      <section className="space-y-3">
        <div className="flex items-end justify-between gap-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
            Installed skills
          </h2>
          <Button
            size="sm"
            variant="outline"
            onClick={() => void reloadInstalled()}
            disabled={loadingInstalled}
          >
            {loadingInstalled ? "Refreshing…" : "Refresh"}
          </Button>
        </div>
        {installedError ? (
          <div className="rounded-lg border border-red-900/50 bg-red-950/40 px-4 py-3 text-sm text-red-200">
            {installedError}
          </div>
        ) : null}
        {loadingInstalled && installed.length === 0 ? (
          <Card>
            <CardContent className="py-8 text-center text-sm text-zinc-500">
              Loading installed skills…
            </CardContent>
          </Card>
        ) : installed.length === 0 ? (
          <Card>
            <CardContent className="py-8 text-center text-sm text-zinc-400">
              No marketplace skills installed yet. Search above or browse popular skills below.
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-3">{installed.map(renderInstalledCard)}</div>
        )}
      </section>

      <section className="space-y-3">
        <div className="flex items-end justify-between gap-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
            Popular on ClawHub
          </h2>
          <Button
            size="sm"
            variant="outline"
            onClick={() => void reloadPopular()}
            disabled={loadingPopular}
          >
            {loadingPopular ? "Refreshing…" : "Refresh"}
          </Button>
        </div>
        {topError ? (
          <div className="rounded-lg border border-red-900/50 bg-red-950/40 px-4 py-3 text-sm text-red-200">
            {topError}
          </div>
        ) : null}
        {loadingPopular && popular.length === 0 ? (
          <Card>
            <CardContent className="py-8 text-center text-sm text-zinc-500">
              Loading popular skills…
            </CardContent>
          </Card>
        ) : popular.length === 0 ? (
          <Card>
            <CardContent className="py-8 text-center text-sm text-zinc-400">
              The configured ClawHub registry returned no popular results (or the registry is
              unreachable).
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-3">{popular.map(renderRemoteCard)}</div>
        )}
      </section>
    </div>
  );
}
