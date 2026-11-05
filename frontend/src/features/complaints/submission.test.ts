import { describe, expect, it } from "vitest";

import {
  DELIVERY_META,
  furthestAllowedStep,
  initialAuthoritySelection,
} from "@/features/complaints/submission";
import type { Authority, AuthorityMatchesResponse, Complaint } from "@/types/api";

const authority = (id: string): Authority => ({
  id,
  name: `Dept ${id}`,
  jurisdiction: "Demo City",
  jurisdiction_level: "CITY",
  city: "Demo City",
  state: "Demo State",
  country: "XX",
  supported_categories: ["ROAD_POTHOLE"],
  official_email: `${id}@demo-city.example`,
  official_phone: null,
  website_url: null,
  source_url: null,
  verified_at: null,
  verification_notes: null,
  service_timeline_days: null,
  parent_authority_id: null,
  is_demo: true,
});

const photo = {
  id: "p1",
  evidence_type: "ORIGINAL" as const,
  file_type: "image/jpeg",
  file_size_bytes: 1,
  width: 1,
  height: 1,
  created_at: "",
  url: "",
};

function complaint(overrides: Partial<Complaint>): Complaint {
  return {
    id: "c1", public_reference: "CP-1", title: null, description: null, category: null, severity: null,
    status: "DRAFT", address_line: null, locality: null, city: null, state: null, postal_code: null,
    country: null, latitude: null, longitude: null, location_confirmed_at: null, observed_at: null,
    draft_subject: null, draft_body: null, authority: null, submitted_at: null, created_at: "",
    updated_at: "", evidence: [], available_actions: [], ...overrides,
  };
}

const details = { title: "Pothole", description: "A deep pothole.", category: "ROAD_POTHOLE" as const };

describe("furthestAllowedStep", () => {
  it.each([
    ["no photo", {}, 1],
    ["photo only", { evidence: [photo] }, 2],
    ["details done", { evidence: [photo], ...details }, 3],
    ["location confirmed", { evidence: [photo], ...details, location_confirmed_at: "x" }, 5],
    ["letter but no department", { evidence: [photo], ...details, location_confirmed_at: "x", draft_body: "Dear" }, 5],
    ["department and letter", { evidence: [photo], ...details, location_confirmed_at: "x", draft_body: "Dear", authority: authority("a") }, 6],
  ])("%s → step %i", (_label, overrides, expected) => {
    expect(furthestAllowedStep(complaint(overrides as Partial<Complaint>))).toBe(expected);
  });
});

describe("initialAuthoritySelection", () => {
  const matches = (confidence: AuthorityMatchesResponse["confidence"], selected: string | null = null) => ({
    confidence,
    selected_authority_id: selected,
    matches: [
      { authority: authority("a"), score: 11, reasons: [] },
      { authority: authority("b"), score: 11, reasons: [] },
    ],
  });

  it("pre-selects a certain match", () => {
    expect(initialAuthoritySelection(matches("EXACT"))).toBe("a");
  });

  it("does not guess when the match is uncertain", () => {
    expect(initialAuthoritySelection(matches("PARTIAL"))).toBeNull();
  });

  it("keeps the citizen's earlier choice", () => {
    expect(initialAuthoritySelection(matches("PARTIAL", "b"))).toBe("b");
  });

  it("selects nothing when nothing matches", () => {
    expect(initialAuthoritySelection({ confidence: "NONE", matches: [], selected_authority_id: null })).toBeNull();
  });
});

describe("DELIVERY_META", () => {
  it("never presents a simulated send as delivered", () => {
    const label = DELIVERY_META.SIMULATED_SENT.label.toLowerCase();
    expect(label).toContain("simulated");
    expect(label).toContain("not delivered");
    expect(DELIVERY_META.FAILED.label).toContain("nothing was delivered");
  });
});
