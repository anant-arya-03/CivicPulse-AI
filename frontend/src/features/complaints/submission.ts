/** Pure rules for the department and submission steps (unit-tested). */

import type { AuthorityMatchesResponse, Complaint, DeliveryStatus } from "@/types/api";

/**
 * The furthest wizard step this draft can be on. Each step needs the earlier ones:
 * 1 photo → 2 details → 3 location → 4 department, 5 letter → 6 submit (needs both 4 and 5).
 */
export function furthestAllowedStep(complaint: Complaint | undefined): number {
  const hasPhoto = Boolean(complaint?.evidence.some((e) => e.evidence_type === "ORIGINAL"));
  if (!complaint || !hasPhoto) return 1;
  if (!complaint.title || !complaint.description || !complaint.category) return 2;
  if (!complaint.location_confirmed_at) return 3;
  if (!complaint.authority || !complaint.draft_body) return 5;
  return 6;
}

/**
 * Which department to pre-select. The citizen always confirms; we only pre-select when the
 * match is certain (EXACT) or they already chose one. Uncertain matches start with no choice.
 */
export function initialAuthoritySelection(data: AuthorityMatchesResponse): string | null {
  if (data.selected_authority_id) return data.selected_authority_id;
  if (data.confidence === "EXACT") return data.matches[0]?.authority.id ?? null;
  return null;
}

export type DeliveryTone = "neutral" | "teal" | "warning" | "success" | "error";

/** How each message status is shown. Simulated sends are never presented as delivered. */
export const DELIVERY_META: Record<DeliveryStatus, { label: string; tone: DeliveryTone }> = {
  DRAFT: { label: "Draft: waiting for your approval", tone: "neutral" },
  APPROVED: { label: "Approved, not sent yet", tone: "neutral" },
  SENDING: { label: "Sending…", tone: "teal" },
  SENT: { label: "Sent", tone: "success" },
  SIMULATED_SENT: { label: "Simulated: not delivered to a real department", tone: "warning" },
  FAILED: { label: "Failed: nothing was delivered", tone: "error" },
  SUPERSEDED: { label: "Replaced by a newer version", tone: "neutral" },
  CANCELLED: { label: "Not sent", tone: "neutral" },
  RECEIVED: { label: "Received", tone: "teal" },
};

/** The badge text for one message. A simulated reply never looks like a real one. */
export function deliveryLabel(status: DeliveryStatus, isSimulated: boolean) {
  if (status === "RECEIVED" && isSimulated) {
    return { label: "Simulated reply: not from a real department", tone: "warning" as const };
  }
  return DELIVERY_META[status];
}
