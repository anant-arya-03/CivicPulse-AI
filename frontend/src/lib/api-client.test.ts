import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest, CSRF_COOKIE_NAME } from "@/lib/api-client";

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("apiRequest", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    document.cookie = `${CSRF_COOKIE_NAME}=test-csrf-token; path=/`;
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
    document.cookie = `${CSRF_COOKIE_NAME}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
  });

  it("calls the relative /api/v1 URL and returns parsed JSON", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { ok: true }));

    await expect(apiRequest("/health")).resolves.toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/health", expect.objectContaining({ method: "GET" }));
  });

  it("sends the CSRF token on state-changing requests", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}));

    await apiRequest("/users/me", { method: "PATCH", body: { name: "Asha" } });

    const init = fetchMock.mock.calls[0]?.[1];
    expect(init?.headers).toMatchObject({
      "X-CSRF-Token": "test-csrf-token",
      "Content-Type": "application/json",
    });
    expect(init?.body).toBe(JSON.stringify({ name: "Asha" }));
  });

  it("does not send the CSRF token on GET requests", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}));
    await apiRequest("/auth/me");
    expect(fetchMock.mock.calls[0]?.[1]?.headers).not.toHaveProperty("X-CSRF-Token");
  });

  it("turns the backend error shape into an ApiError", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(401, {
        error: { code: "UNAUTHENTICATED", message: "Please log in to continue.", details: {} },
      }),
    );

    const error = await apiRequest("/auth/me").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 401,
      code: "UNAUTHENTICATED",
      message: "Please log in to continue.",
    });
  });

  it("uses a friendly message when the response has no JSON body", async () => {
    fetchMock.mockResolvedValue(new Response("<html>Bad Gateway</html>", { status: 502 }));
    await expect(apiRequest("/health")).rejects.toMatchObject({
      status: 502,
      message: "Something went wrong. Please try again.",
    });
  });

  it("reports network failures as NETWORK_ERROR", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    await expect(apiRequest("/health")).rejects.toMatchObject({ status: 0, code: "NETWORK_ERROR" });
  });

  it("returns undefined for 204 No Content", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    await expect(apiRequest("/auth/logout", { method: "POST" })).resolves.toBeUndefined();
  });
});
