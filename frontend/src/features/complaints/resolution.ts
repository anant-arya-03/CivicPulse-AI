import type { ComplaintStatus, ResolutionAssessment, ResolutionReview } from "@/types/api";

type Tone = "success" | "warning" | "error" | "neutral";

/** The AI's verdict, always worded as an opinion ("appears"), never as a fact. */
export const ASSESSMENT_META: Record<ResolutionAssessment["assessment"], { label: string; tone: Tone }> = {
  APPEARS_RESOLVED: { label: "Appears repaired", tone: "success" },
  PARTIALLY_RESOLVED: { label: "Appears partly repaired", tone: "warning" },
  NOT_RESOLVED: { label: "The problem appears to still be there", tone: "error" },
  CANNOT_DETERMINE: { label: "Can't tell from these photos", tone: "neutral" },
};

export const CONFIDENCE_LABEL: Record<ResolutionAssessment["confidence"], string> = {
  HIGH: "high confidence",
  MEDIUM: "medium confidence",
  LOW: "low confidence",
};

export const DECISION_META: Record<ResolutionReview["decision"], { label: string; tone: Tone }> = {
  PENDING: { label: "Waiting for your decision", tone: "warning" },
  CONFIRMED_RESOLVED: { label: "You confirmed it's fixed", tone: "success" },
  DISPUTED: { label: "You said it's not fixed", tone: "error" },
  SUPERSEDED: { label: "Replaced by a newer photo", tone: "neutral" },
};

/** The check waiting for the citizen's decision, if any (at most one exists). */
export function pendingReview(reviews: ResolutionReview[] | undefined): ResolutionReview | null {
  return reviews?.find((review) => review.decision === "PENDING") ?? null;
}

/** "It's not fixed" only makes sense after the department reported a repair. */
export function canDispute(status: ComplaintStatus): boolean {
  return status === "RESOLVED_PENDING_VERIFICATION";
}
