import { describe, expect, it } from "vitest";
import { CONNECTION_RESET_KEEP_KEYS, resetConnectionState } from "../resetConnectionState";

describe("resetConnectionState", () => {
  it("clears connection keys but keeps theme keys", () => {
    localStorage.setItem("aethos_web_v1", "{}");
    localStorage.setItem("nexa-theme", "dark");
    localStorage.setItem("nexa-appearance", "compact");
    localStorage.setItem("nexaShowUsageDetails", "true");
    sessionStorage.setItem("x", "y");

    resetConnectionState();

    expect(localStorage.getItem("aethos_web_v1")).toBeNull();
    expect(localStorage.getItem("nexaShowUsageDetails")).toBeNull();
    expect(localStorage.getItem("nexa-theme")).toBe("dark");
    expect(localStorage.getItem("nexa-appearance")).toBe("compact");
    expect(sessionStorage.length).toBe(0);
    expect(CONNECTION_RESET_KEEP_KEYS.has("nexa-theme")).toBe(true);
  });
});
