import { afterEach, describe, expect, it, vi } from "vitest";
import { diagnoseConnection } from "../diagnoseConnection";

describe("diagnoseConnection", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("marks healthReachable when configured base returns 200", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("ok", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const d = await diagnoseConnection("http://127.0.0.1:8010");
    expect(d.healthReachable).toBe(true);
    expect(d.alternateReachable).toBe(false);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8010/api/v1/health",
      expect.any(Object),
    );
  });

  it("finds suggested API base when configured host fails but default works", async () => {
    let call = 0;
    const fetchMock = vi.fn().mockImplementation(() => {
      call += 1;
      if (call === 1) {
        return Promise.reject(new TypeError("Failed to fetch"));
      }
      return Promise.resolve(new Response("ok", { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const d = await diagnoseConnection("http://127.0.0.1:8120");
    expect(d.healthReachable).toBe(false);
    expect(d.alternateReachable).toBe(true);
    expect(d.suggestedApiBase).toBeTruthy();
  });
});
