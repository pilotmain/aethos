import { describe, expect, it, beforeEach } from "vitest";
import {
  clearSavedBearerToken,
  readConfig,
  saveConfig,
  WEB_API_BASE_STORAGE_KEY,
  WEB_BEARER_TOKEN_STORAGE_KEY,
  WEB_CONFIG_STORAGE_KEY,
  WEB_USER_ID_STORAGE_KEY,
} from "@/lib/config";

describe("web config", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("reads standalone Connection settings keys", () => {
    window.localStorage.setItem(WEB_API_BASE_STORAGE_KEY, "http://127.0.0.1:8120/");
    window.localStorage.setItem(WEB_USER_ID_STORAGE_KEY, "tg_1603429832");
    window.localStorage.setItem(WEB_BEARER_TOKEN_STORAGE_KEY, "secret-token");

    expect(readConfig()).toEqual({
      apiBase: "http://127.0.0.1:8120",
      userId: "tg_1603429832",
      token: "secret-token",
    });
  });

  it("keeps canonical JSON and standalone keys in sync", () => {
    saveConfig({
      apiBase: "http://127.0.0.1:8010",
      userId: "tg_1603429832",
      token: "secret-token",
    });

    expect(window.localStorage.getItem(WEB_CONFIG_STORAGE_KEY)).toContain("secret-token");
    expect(window.localStorage.getItem(WEB_API_BASE_STORAGE_KEY)).toBe("http://127.0.0.1:8010");
    expect(window.localStorage.getItem(WEB_USER_ID_STORAGE_KEY)).toBe("tg_1603429832");
    expect(window.localStorage.getItem(WEB_BEARER_TOKEN_STORAGE_KEY)).toBe("secret-token");

    clearSavedBearerToken();

    expect(readConfig()).toMatchObject({
      apiBase: "http://127.0.0.1:8010",
      userId: "tg_1603429832",
      token: "",
    });
    expect(window.localStorage.getItem(WEB_BEARER_TOKEN_STORAGE_KEY)).toBeNull();
  });
});
