import { describe, expect, it } from "vitest";

import { planSuggestions } from "@/features/complaints/ai-suggestions";
import { letterSchema } from "@/features/complaints/schemas";
import type { VisionAnalysis } from "@/types/api";

const analysis: VisionAnalysis = {
  is_civic_issue: true,
  category: "ROAD_POTHOLE",
  category_confidence: "HIGH",
  suggested_title: "Pothole on the road surface",
  suggested_description: "A pothole is visible on the road surface.",
  severity: "MEDIUM",
  observations: [],
  uncertainties: [],
  warnings: [],
};

const empty = { title: "", category: "" as never, severity: "UNKNOWN" as const, description: "" };

describe("planSuggestions", () => {
  it("fills every empty field", () => {
    const plan = planSuggestions(empty, {}, analysis);
    expect(plan.fill).toEqual({
      title: "Pothole on the road surface",
      category: "ROAD_POTHOLE",
      severity: "MEDIUM",
      description: "A pothole is visible on the road surface.",
    });
    expect(plan.alternatives).toEqual({});
  });

  it("never overwrites what the citizen typed, and offers the suggestion instead", () => {
    const plan = planSuggestions({ ...empty, title: "Huge hole near my house" }, {}, analysis);
    expect(plan.fill.title).toBeUndefined();
    expect(plan.alternatives.title).toBe("Pothole on the road surface");
    expect(plan.fill.description).toBe("A pothole is visible on the road surface.");
  });

  it("treats a field the citizen touched as theirs, even if they cleared it", () => {
    const plan = planSuggestions(empty, { title: true }, analysis);
    expect(plan.fill.title).toBeUndefined();
    expect(plan.alternatives.title).toBe("Pothole on the road surface");
  });

  it("treats the default severity 'Not sure' as empty", () => {
    expect(planSuggestions(empty, {}, analysis).fill.severity).toBe("MEDIUM");
  });

  it("keeps a severity the citizen chose", () => {
    const plan = planSuggestions({ ...empty, severity: "HIGH" }, {}, analysis);
    expect(plan.fill.severity).toBeUndefined();
    expect(plan.alternatives.severity).toBe("MEDIUM");
  });

  it("does not offer a suggestion that matches the citizen's value", () => {
    const plan = planSuggestions({ ...empty, category: "ROAD_POTHOLE" }, {}, analysis);
    expect(plan.fill.category).toBeUndefined();
    expect(plan.alternatives.category).toBeUndefined();
  });

  it("never offers 'Not sure' as a replacement for a severity the citizen chose", () => {
    const plan = planSuggestions({ ...empty, severity: "LOW" }, {}, { ...analysis, severity: "UNKNOWN" });
    expect(plan.alternatives.severity).toBeUndefined();
  });
});

describe("letterSchema", () => {
  it("accepts a normal letter", () => {
    expect(
      letterSchema.safeParse({ subject: "Pothole on Lake Road", body: "Dear Sir or Madam, please fix it." })
        .success,
    ).toBe(true);
  });

  it("requires a subject and a body of reasonable length", () => {
    expect(letterSchema.safeParse({ subject: "Hi", body: "Dear Sir or Madam, please fix it." }).success).toBe(false);
    expect(letterSchema.safeParse({ subject: "Pothole on Lake Road", body: "Fix it" }).success).toBe(false);
  });
});
