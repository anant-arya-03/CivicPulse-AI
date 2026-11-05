import { describe, expect, it } from "vitest";

import { getSafeRedirect } from "@/lib/safe-redirect";

describe("getSafeRedirect", () => {
  it("allows same-site paths", () => {
    expect(getSafeRedirect("/complaints/123")).toBe("/complaints/123");
    expect(getSafeRedirect("/settings?tab=privacy")).toBe("/settings?tab=privacy");
  });

  it.each([null, undefined, "", "https://evil.example", "//evil.example", "/\\evil.example", "dashboard"])(
    "falls back to /dashboard for unsafe value %s",
    (value) => {
      expect(getSafeRedirect(value)).toBe("/dashboard");
    },
  );

  it("never redirects back to the auth pages", () => {
    expect(getSafeRedirect("/login")).toBe("/dashboard");
    expect(getSafeRedirect("/register?x=1")).toBe("/dashboard");
  });
});
