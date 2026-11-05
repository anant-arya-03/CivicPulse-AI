import { describe, expect, it } from "vitest";

import { ASSESSMENT_META, DECISION_META, canDispute, pendingReview } from "@/features/complaints/resolution";
import type { ComplaintStatus, ResolutionReview } from "@/types/api";

describe("resolution labels", () => {
  it("words every AI verdict as an opinion, never as a fact", () => {
    for (const { label } of Object.values(ASSESSMENT_META)) {
      expect(label.toLowerCase()).not.toMatch(/\b(is|definitely) (fixed|resolved)\b/);
    }
    expect(ASSESSMENT_META.APPEARS_RESOLVED.label).toBe("Appears repaired");
  });

  it("names every decision from the citizen's point of view", () => {
    expect(DECISION_META.CONFIRMED_RESOLVED.label).toContain("You confirmed");
    expect(DECISION_META.DISPUTED.label).toContain("You said");
  });
});

describe("pendingReview", () => {
  const review = (id: string, decision: ResolutionReview["decision"]) => ({ id, decision }) as ResolutionReview;

  it("finds the check waiting for a decision", () => {
    expect(pendingReview([review("a", "SUPERSEDED"), review("b", "PENDING")])?.id).toBe("b");
    expect(pendingReview([review("a", "CONFIRMED_RESOLVED")])).toBeNull();
    expect(pendingReview(undefined)).toBeNull();
  });
});

describe("canDispute", () => {
  it("allows 'not fixed' only after the department reported a repair", () => {
    const statuses: ComplaintStatus[] = ["SUBMITTED", "ACKNOWLEDGED", "IN_PROGRESS", "REOPENED", "VERIFIED_RESOLVED"];
    for (const status of statuses) expect(canDispute(status)).toBe(false);
    expect(canDispute("RESOLVED_PENDING_VERIFICATION")).toBe(true);
  });
});
