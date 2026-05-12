import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AssignTaskDialog } from "../AssignTaskDialog";

const createAgentAssignmentMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api/assignments", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/assignments")>("@/lib/api/assignments");
  return { ...actual, createAgentAssignment: createAgentAssignmentMock };
});

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    formatMissionControlApiError: (s: string) => s,
  };
});

afterEach(() => {
  createAgentAssignmentMock.mockReset();
});

describe("AssignTaskDialog", () => {
  it("opens, validates required title, and submits via createAgentAssignment", async () => {
    createAgentAssignmentMock.mockResolvedValue({
      id: 42,
      assigned_to_handle: "security_agent",
      auto_dispatch: { ok: true, assignment_id: 42 },
    });
    const onAssigned = vi.fn();
    render(
      <AssignTaskDialog
        agentHandle="security_agent"
        agentDisplayName="security_agent"
        agentDomain="security"
        onAssigned={onAssigned}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Assign task/i }));
    expect(await screen.findByText(/Assign task to @security_agent/i)).toBeInTheDocument();

    const submit = screen.getByRole("button", { name: /Create & dispatch/i });
    expect(submit).toBeDisabled();

    const title = screen.getByLabelText(/Task title/i);
    fireEvent.change(title, { target: { value: "Run security scan" } });
    expect(submit).not.toBeDisabled();

    const description = screen.getByLabelText(/Description/i);
    fireEvent.change(description, { target: { value: "scan /Users/example/aethos" } });

    fireEvent.click(screen.getByLabelText("High"));

    fireEvent.click(submit);

    await waitFor(() => expect(createAgentAssignmentMock).toHaveBeenCalledTimes(1));
    expect(createAgentAssignmentMock).toHaveBeenCalledWith({
      assigned_to_handle: "security_agent",
      title: "Run security scan",
      description: "scan /Users/example/aethos",
      priority: "high",
    });
    await waitFor(() => expect(onAssigned).toHaveBeenCalledTimes(1));
  });

  it("trigger is disabled when ``disabled`` is true", () => {
    render(
      <AssignTaskDialog
        agentHandle="security_agent"
        disabled
        disabledReason="Agent is busy"
      />,
    );
    const trigger = screen.getByRole("button", { name: /Assign task/i });
    expect(trigger).toBeDisabled();
    expect(trigger).toHaveAttribute("title", "Agent is busy");
  });

  it("renders inline error when create fails", async () => {
    createAgentAssignmentMock.mockRejectedValue(new Error("409: duplicate"));
    render(<AssignTaskDialog agentHandle="security_agent" agentDisplayName="security_agent" />);
    fireEvent.click(screen.getByRole("button", { name: /Assign task/i }));
    fireEvent.change(await screen.findByLabelText(/Task title/i), { target: { value: "dup" } });
    fireEvent.click(screen.getByRole("button", { name: /Create & dispatch/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("409: duplicate");
  });
});
