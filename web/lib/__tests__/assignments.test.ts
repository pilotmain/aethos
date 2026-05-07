import { describe, expect, it } from "vitest";

import {
  groupAssignmentsByAgent,
  isAssignmentTerminal,
  summarizeAssignments,
  type AgentAssignmentRow,
} from "@/lib/api/assignments";

function row(partial: Partial<AgentAssignmentRow>): AgentAssignmentRow {
  return {
    id: 0,
    user_id: "u",
    organization_id: 1,
    parent_assignment_id: null,
    assigned_to_handle: "agent",
    assigned_to_handle_display: null,
    assigned_by_handle: "user",
    assigned_by_handle_display: null,
    title: "t",
    description: "",
    status: "queued",
    priority: "normal",
    input_json: {},
    output_json: null,
    error: null,
    channel: "web",
    web_session_id: null,
    started_at: null,
    completed_at: null,
    created_at: null,
    updated_at: null,
    ...partial,
  };
}

describe("agent assignments client helpers", () => {
  it("groups by display handle, falling back to handle", () => {
    const grouped = groupAssignmentsByAgent([
      row({ id: 1, assigned_to_handle: "research_analyst" }),
      row({ id: 2, assigned_to_handle: "research_analyst", assigned_to_handle_display: "Research Analyst" }),
      row({ id: 3, assigned_to_handle: "" }),
    ]);
    expect(Object.keys(grouped).sort()).toEqual(["Research Analyst", "research_analyst", "unassigned"]);
    expect(grouped["research_analyst"]).toHaveLength(1);
    expect(grouped["Research Analyst"]).toHaveLength(1);
    expect(grouped["unassigned"]).toHaveLength(1);
  });

  it("summarizes counts across statuses", () => {
    const s = summarizeAssignments([
      row({ status: "running" }),
      row({ status: "queued" }),
      row({ status: "completed" }),
      row({ status: "failed" }),
      row({ status: "cancelled" }),
    ]);
    expect(s).toEqual({ total: 5, running: 2, completed: 1, failed: 1 });
  });

  it("classifies terminal statuses", () => {
    expect(isAssignmentTerminal("completed")).toBe(true);
    expect(isAssignmentTerminal("failed")).toBe(true);
    expect(isAssignmentTerminal("cancelled")).toBe(true);
    expect(isAssignmentTerminal("running")).toBe(false);
    expect(isAssignmentTerminal("")).toBe(false);
  });
});
