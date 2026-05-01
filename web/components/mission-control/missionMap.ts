import type { LuminousStatus } from "./LuminousNode";
import type { MissionControlSummary } from "@/lib/nexa-types";

/** Exported for Mission Control cleanup (spawn group scope). */
export const MISSION_MAP_UNGROUPED_KEY = "__ungrouped__";

const UNGROUPED = MISSION_MAP_UNGROUPED_KEY;

/** Map durable assignment status strings → luminous node status (server truth). */
export function mapAssignmentStatus(raw: string | null | undefined): LuminousStatus {
  const s = (raw ?? "").trim().toLowerCase();
  if (!s) return "queued";
  if (s.includes("fail")) return "failed";
  if (s.includes("complete") || s.includes("done")) return "completed";
  if (s.includes("block")) return "blocked";
  if (s.includes("wait") && s.includes("approval")) return "waiting_approval";
  if (s.includes("waiting") && s.includes("worker")) return "waiting_worker";
  if (s.includes("run")) return "running";
  if (s.includes("queue")) return "queued";
  return "queued";
}

export type LuminousNodeVM = {
  key: string;
  handle: string;
  status: LuminousStatus;
  label: string;
};

export type MissionMapGroupVM = {
  groupKey: string;
  heading: string;
  nodes: LuminousNodeVM[];
};

function spawnGroupIdFromAssignment(a: {
  spawn_group_id?: string | null;
  input_json?: Record<string, unknown> | null;
}): string {
  const top = (a.spawn_group_id ?? "").trim();
  if (top) return top;
  const ij = a.input_json;
  if (ij && typeof ij === "object") {
    const s = (ij as Record<string, unknown>).spawn_group_id;
    if (typeof s === "string" && s.trim()) return s.trim();
  }
  return "";
}

function isCancelled(status: string | null | undefined): boolean {
  return (status ?? "").trim().toLowerCase() === "cancelled";
}

function isSpawnParent(a: {
  input_json?: Record<string, unknown> | null;
}): boolean {
  const ij = a.input_json;
  if (!ij || typeof ij !== "object") return false;
  return (ij as Record<string, unknown>).kind === "spawn_parent";
}

/**
 * Groups orchestration assignments by spawn_group_id; drops cancelled rows and stale
 * duplicate rows (same spawn group + agent handle keeps newest assignment id).
 */
export function orchestrationToMissionMapGroups(data: MissionControlSummary | null): MissionMapGroupVM[] {
  const rows = data?.orchestration?.assignments;
  if (!rows?.length) return [];

  const alive = rows.filter((a) => !isCancelled(a.status)).filter((a) => !isSpawnParent(a));

  const byNewestFirst = [...alive].sort((a, b) => b.id - a.id);
  const seen = new Set<string>();
  const picked: typeof alive = [];
  for (const a of byNewestFirst) {
    const sg = spawnGroupIdFromAssignment(a);
    const handle = (a.assigned_to_handle ?? "").replace(/^@/, "").trim().toLowerCase();
    let dedupeKey: string;
    if (sg) {
      dedupeKey = `${sg}\n${handle}`;
    } else {
      dedupeKey = `solo\n${a.id}`;
    }
    if (seen.has(dedupeKey)) continue;
    seen.add(dedupeKey);
    picked.push(a);
  }

  const groupMap = new Map<string, LuminousNodeVM[]>();
  for (const a of picked) {
    const sg = spawnGroupIdFromAssignment(a);
    const gkey = sg || UNGROUPED;
    const vm: LuminousNodeVM = {
      key: `a-${a.id}`,
      handle: (a.assigned_to_handle_display ?? a.assigned_to_handle).replace(/^@/, ""),
      status: mapAssignmentStatus(a.status),
      label: a.title,
    };
    const arr = groupMap.get(gkey) ?? [];
    arr.push(vm);
    groupMap.set(gkey, arr);
  }

  const entries = Array.from(groupMap.entries()).map(([groupKey, nodes]) => {
    let heading: string;
    if (groupKey === UNGROUPED) heading = "Ungrouped";
    else heading = groupKey;
    return { groupKey, heading, nodes };
  });

  entries.sort((a, b) => {
    if (a.groupKey === UNGROUPED) return 1;
    if (b.groupKey === UNGROUPED) return -1;
    return a.heading.localeCompare(b.heading);
  });

  return entries;
}

/** Flat list (legacy): same filtering as groups, single strip. */
export function orchestrationToLuminousNodes(data: MissionControlSummary | null): LuminousNodeVM[] {
  return orchestrationToMissionMapGroups(data).flatMap((g) => g.nodes);
}
