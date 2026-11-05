import { describe, expect, it } from "vitest";

import {
  ATTENTION_META,
  REPLY_KIND_CHOICES,
  REPLY_KIND_META,
  deadlineSentence,
  reminderCount,
} from "@/features/complaints/monitoring";
import { DELIVERY_META, deliveryLabel } from "@/features/complaints/submission";
import type { MonitoringState } from "@/types/api";

function monitoringState(overrides: Partial<MonitoringState> = {}): MonitoringState {
  return {
    monitored: true,
    response_due_at: "2026-11-11T10:00:00Z",
    deadline_basis: "the response time listed for this department (7 days)",
    deadline_official: true,
    followups_sent: 0,
    followups_max: 2,
    authority_reference_number: null,
    open_followup: null,
    open_followup_sha256: null,
    replies_to_review: [],
    latest_reply: null,
    escalation: null,
    ...overrides,
  };
}

describe("deadlineSentence", () => {
  it("explains when and why CivicPulse will check", () => {
    const text = deadlineSentence(monitoringState());
    expect(text).toContain("11 Nov 2026");
    expect(text).toContain("listed for this department (7 days)");
    expect(text).toContain("suggest a reminder");
  });

  it("says nothing when no check is scheduled", () => {
    expect(deadlineSentence(monitoringState({ response_due_at: null }))).toBeNull();
  });
});

describe("reminderCount", () => {
  it("shows how many of the allowed reminders were sent", () => {
    expect(reminderCount(monitoringState({ followups_sent: 1 }))).toBe("1 of 2 reminders sent");
    expect(reminderCount(monitoringState({ followups_max: 1 }))).toBe("0 of 1 reminder sent");
  });
});

describe("reply meanings", () => {
  it("offers every meaning, and none of them claims the problem is fixed", () => {
    expect(new Set(REPLY_KIND_CHOICES)).toEqual(new Set(Object.keys(REPLY_KIND_META)));
    expect(REPLY_KIND_META.RESOLVED_CLAIM.effect).toContain("Only you can confirm");
  });

  it("labels every attention kind", () => {
    for (const meta of Object.values(ATTENTION_META)) expect(meta.label.length).toBeGreaterThan(3);
  });
});

describe("delivery labels", () => {
  it("never presents a simulated reply as a real one", () => {
    expect(deliveryLabel("RECEIVED", true).label).toContain("Simulated reply");
    expect(deliveryLabel("RECEIVED", false).label).toBe("Received");
  });

  it("never claims an unsent reminder was sent", () => {
    expect(DELIVERY_META.DRAFT.label.toLowerCase()).toContain("waiting for your approval");
    expect(DELIVERY_META.CANCELLED.label).toBe("Not sent");
  });
});
