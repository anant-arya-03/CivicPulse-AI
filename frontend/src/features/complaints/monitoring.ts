import { formatDate } from "@/lib/format";
import type { AttentionKind, MonitoringState, ReplyKind } from "@/types/api";

/** What each reply meaning is called, and what it does (the backend rules decide the effect). */
export const REPLY_KIND_META: Record<ReplyKind, { label: string; effect: string }> = {
  ACKNOWLEDGMENT: {
    label: "Acknowledged",
    effect: "Marks the complaint as acknowledged. We keep watching for progress.",
  },
  IN_PROGRESS: {
    label: "Work in progress",
    effect: "Marks the complaint as in progress. We keep watching for updates.",
  },
  RESOLVED_CLAIM: {
    label: "Says it's fixed",
    effect: "Stops reminders. Only you can confirm that it is really fixed.",
  },
  REQUEST_FOR_INFO: {
    label: "Asks for more information",
    effect: "Stops reminders while you reply to the department.",
  },
  REJECTION: {
    label: "Declines the complaint",
    effect: "Stops reminders and shows who you can escalate to.",
  },
  UNRELATED: {
    label: "Not about this complaint",
    effect: "Changes nothing (for example an automatic out-of-office reply).",
  },
};

/** Order of the choices when the citizen says what a reply means. */
export const REPLY_KIND_CHOICES: ReplyKind[] = [
  "ACKNOWLEDGMENT",
  "IN_PROGRESS",
  "RESOLVED_CLAIM",
  "REQUEST_FOR_INFO",
  "REJECTION",
  "UNRELATED",
];

export const ATTENTION_META: Record<AttentionKind, { label: string; tone: "warning" | "error" | "teal" }> = {
  VERIFY_FIX: { label: "Check the fix", tone: "teal" },
  FOLLOWUP_FAILED: { label: "Reminder failed", tone: "error" },
  FOLLOWUP_READY: { label: "Reminder to review", tone: "warning" },
  REPLY_TO_REVIEW: { label: "Reply to review", tone: "warning" },
  INFO_REQUESTED: { label: "Information requested", tone: "warning" },
  ESCALATION: { label: "Escalation suggested", tone: "error" },
};

/** "We'll check for a reply on 11 Nov 2026, based on …" or null when nothing is scheduled. */
export function deadlineSentence(state: MonitoringState): string | null {
  if (!state.response_due_at) return null;
  const when = formatDate(state.response_due_at);
  return state.deadline_basis
    ? `If there's no reply by ${when}, we'll suggest a reminder (based on ${state.deadline_basis}).`
    : `If there's no reply by ${when}, we'll suggest a reminder.`;
}

/** "1 of 2 reminders sent" */
export function reminderCount(state: MonitoringState): string {
  const noun = state.followups_max === 1 ? "reminder" : "reminders";
  return `${state.followups_sent} of ${state.followups_max} ${noun} sent`;
}
