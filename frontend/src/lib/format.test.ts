import { describe, expect, it } from "vitest";

import { formatFileSize, formatRelative } from "@/lib/format";

describe("formatRelative", () => {
  const now = new Date("2026-11-03T12:00:00Z");

  it.each([
    ["2026-11-03T11:59:30Z", "just now"],
    ["2026-11-03T11:55:00Z", "5 minutes ago"],
    ["2026-11-03T09:00:00Z", "3 hours ago"],
    ["2026-11-02T12:00:00Z", "yesterday"],
    ["2026-10-20T12:00:00Z", "2 weeks ago"],
  ])("formats %s as %s", (iso, expected) => {
    expect(formatRelative(iso, now)).toBe(expected);
  });
});

describe("formatFileSize", () => {
  it.each([
    [512, "512 B"],
    [2048, "2 KB"],
    [3.5 * 1024 * 1024, "3.5 MB"],
  ])("formats %d bytes as %s", (bytes, expected) => {
    expect(formatFileSize(bytes)).toBe(expected);
  });
});
