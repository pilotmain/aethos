"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { AddMemberDialog } from "@/components/mission-control/Team/AddMemberDialog";
import { MemberList } from "@/components/mission-control/Team/MemberList";
import { OrgChart } from "@/components/mission-control/Team/OrgChart";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { formatMissionControlApiError } from "@/lib/api";
import {
  fetchGovernanceMe,
  fetchOrgMembers,
  patchOrgMember,
  postOrgMember,
} from "@/lib/api/governance";
import { fetchMissionControlState } from "@/lib/api/mission-control-state";
import {
  agentRolesToTeamMembers,
  buildAgentOrgChart,
  governanceRowsToTeamMembers,
  orchestrationFromState,
} from "@/lib/api/team";
import { readConfig } from "@/lib/config";
import type { OrgChartNode, TeamMember } from "@/types/mission-control";
import Link from "next/link";

export default function MissionControlTeamPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionErr, setActionErr] = useState<string | null>(null);
  const [agents, setAgents] = useState<TeamMember[]>([]);
  const [humans, setHumans] = useState<TeamMember[]>([]);
  const [orgChart, setOrgChart] = useState<OrgChartNode[]>([]);
  const [govEnabled, setGovEnabled] = useState(false);
  const [orgId, setOrgId] = useState<string | null>(null);

  const currentUserId = useMemo(() => (readConfig().userId || "").trim(), []);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [state, me] = await Promise.all([fetchMissionControlState(48), fetchGovernanceMe()]);
      const { roles, assignments } = orchestrationFromState(state);
      setAgents(agentRolesToTeamMembers(roles, assignments));
      setOrgChart(buildAgentOrgChart(roles));

      setGovEnabled(Boolean(me.governance_enabled));
      const oid =
        (me.default_organization_id && me.default_organization_id.trim()) ||
        (me.organizations?.[0]?.id ?? "").trim() ||
        null;
      setOrgId(oid);

      if (me.governance_enabled && oid) {
        try {
          const rows = await fetchOrgMembers(oid);
          setHumans(governanceRowsToTeamMembers(rows, oid));
        } catch (e) {
          setHumans([]);
          setError(
            (prev) =>
              prev ||
              (e instanceof Error ? formatMissionControlApiError(e.message) : "Could not load org members."),
          );
        }
      } else {
        setHumans([]);
      }
    } catch (e) {
      setError(e instanceof Error ? formatMissionControlApiError(e.message) : "Failed to load team.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const onInvite = async (userId: string, role: string) => {
    setActionErr(null);
    if (!orgId) throw new Error("No organization selected.");
    await postOrgMember(orgId, { user_id: userId, role });
    await reload();
  };

  const onRoleChange = async (userId: string, newRole: string) => {
    setActionErr(null);
    if (!orgId) return;
    try {
      await patchOrgMember(orgId, userId, { role: newRole });
      await reload();
    } catch (e) {
      setActionErr(e instanceof Error ? formatMissionControlApiError(e.message) : "Role update failed.");
    }
  };

  const onRemove = async (userId: string) => {
    setActionErr(null);
    if (!orgId) return;
    if (
      !window.confirm(
        "Disable this member for this organization? (There is no hard-delete endpoint — they will be marked inactive.)",
      )
    ) {
      return;
    }
    try {
      await patchOrgMember(orgId, userId, { enabled: false });
      await reload();
    } catch (e) {
      setActionErr(e instanceof Error ? formatMissionControlApiError(e.message) : "Remove failed.");
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-700 border-t-violet-500" />
        <p className="text-sm text-zinc-500">Loading team…</p>
      </div>
    );
  }

  const addDisabled = !govEnabled || !orgId;
  const addReason = !govEnabled
    ? "Enable NEXA_GOVERNANCE_ENABLED on the API to manage human members."
    : !orgId
      ? "No organization id — complete governance bootstrap or set NEXA_DEFAULT_ORGANIZATION_ID."
      : undefined;

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-zinc-50">Team</h2>
          <p className="mt-1 max-w-prose text-sm text-zinc-400">
            Agent hierarchy from Mission Control orchestration; organization members from Governance API when enabled.
          </p>
          <p className="mt-2 text-xs text-zinc-600">
            Backend routes:{" "}
            <code className="rounded bg-zinc-900 px-1 py-0.5 font-mono text-[11px]">
              /api/v1/governance/organizations/&#123;org&#125;/members
            </code>{" "}
            (not <code className="font-mono">/org/...</code>).
          </p>
        </div>
        <AddMemberDialog onInvite={onInvite} disabled={addDisabled} disabledReason={addReason} />
      </div>

      {error ? (
        <div className="rounded-lg border border-amber-900/60 bg-amber-950/40 px-4 py-3 text-sm text-amber-100">
          {error}{" "}
          <button type="button" className="ml-2 text-violet-400 underline" onClick={() => void reload()}>
            Retry
          </button>
        </div>
      ) : null}

      {actionErr ? (
        <div className="rounded-lg border border-red-900/60 bg-red-950/40 px-4 py-3 text-sm text-red-100">
          {actionErr}
        </div>
      ) : null}

      <Tabs defaultValue="list" className="space-y-4">
        <TabsList>
          <TabsTrigger value="list">Members</TabsTrigger>
          <TabsTrigger value="hierarchy">Org chart</TabsTrigger>
        </TabsList>

        <TabsContent value="list" className="space-y-10">
          <MemberList
            title="Agents"
            description="From Agent Organization role assignments (Mission Control orchestration)."
            members={agents}
            currentUserId={currentUserId}
          />
          <MemberList
            title="Organization members"
            description={
              govEnabled
                ? "Governance memberships for the active organization."
                : "Governance disabled — enable NEXA_GOVERNANCE_ENABLED to list human members."
            }
            members={humans}
            currentUserId={currentUserId}
            onRoleChange={govEnabled && orgId ? onRoleChange : undefined}
            onRemove={govEnabled && orgId ? onRemove : undefined}
          />
          {!agents.length && !humans.length ? (
            <div className="rounded-xl border border-dashed border-zinc-800 py-12 text-center text-sm text-zinc-500">
              No agents or org members found.{" "}
              <Link className="text-violet-400 underline" href="/mission-control/legacy">
                Open classic Mission Control
              </Link>{" "}
              to configure agents, or add governance members when enabled.
            </div>
          ) : null}
        </TabsContent>

        <TabsContent value="hierarchy">
          <OrgChart nodes={orgChart} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
