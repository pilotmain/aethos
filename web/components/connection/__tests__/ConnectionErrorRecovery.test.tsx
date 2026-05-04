import { render, screen } from "@testing-library/react";
import React, { type ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import type { ConnectionDiagnosis } from "@/lib/connection/types";
import { ConnectionErrorRecovery } from "../ConnectionErrorRecovery";

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

vi.mock("@/lib/config", () => ({
  applyApiBaseAndReload: vi.fn(),
  DEFAULT_API_BASE: "http://127.0.0.1:8010",
  readConfig: () => ({ apiBase: "http://127.0.0.1:8120", userId: "", token: "" }),
  saveConfig: vi.fn(),
}));

describe("ConnectionErrorRecovery", () => {
  it("shows Switch when diagnosis finds alternate base", () => {
    const diagnosis: ConnectionDiagnosis = {
      apiBase: "http://127.0.0.1:8120",
      healthReachable: false,
      corsOk: false,
      alternateReachable: true,
      suggestedApiBase: "http://127.0.0.1:8010",
    };
    const onRetry = vi.fn();
    render(
      <ConnectionErrorRecovery
        dataError="Cannot reach API (example)"
        diagnosis={diagnosis}
        onRetry={onRetry}
      />,
    );
    expect(screen.getByRole("button", { name: /Switch to 8010/i })).toBeInTheDocument();
    expect(screen.getByText(/Your browser is using API base/i)).toBeInTheDocument();
  });

  it("shows session stale guidance for 401 when health works", () => {
    const diagnosis: ConnectionDiagnosis = {
      apiBase: "http://127.0.0.1:8010",
      healthReachable: true,
      corsOk: true,
      alternateReachable: false,
    };
    render(
      <ConnectionErrorRecovery
        dataError="401: Unauthorized (check X-User-Id and optional bearer token)"
        diagnosis={diagnosis}
        onRetry={vi.fn()}
      />,
    );
    expect(screen.getByText(/login\/session looks stale/i)).toBeInTheDocument();
  });
});
