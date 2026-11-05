import {
  Ban,
  CameraIcon,
  CircleCheckBig,
  CircleX,
  BadgeCheck,
  BellOff,
  BellRing,
  Bot,
  Building2,
  Camera,
  CheckCircle2,
  Circle,
  FilePlus2,
  Hash,
  ImageMinus,
  MailMinus,
  MailPlus,
  MailCheck,
  MailX,
  MapPinCheck,
  MessageSquareReply,
  PencilLine,
  RefreshCw,
  RotateCcw,
  ScanSearch,
  Send,
  ShieldAlert,
  Sparkles,
  TriangleAlert,
  Undo2,
  type LucideIcon,
} from "lucide-react";

import { formatDateTime } from "@/lib/format";
import type { ComplaintEvent } from "@/types/api";

const EVENT_ICONS: Record<string, LucideIcon> = {
  COMPLAINT_CREATED: FilePlus2,
  EVIDENCE_UPLOADED: Camera,
  EVIDENCE_REMOVED: ImageMinus,
  DETAILS_UPDATED: PencilLine,
  LOCATION_CONFIRMED: MapPinCheck,
  STATUS_CHANGED: RefreshCw,
  COMPLAINT_CANCELLED: Ban,
  COMPLAINT_CLOSED: CheckCircle2,
  AI_ANALYSIS_COMPLETED: Sparkles,
  AI_ANALYSIS_FAILED: TriangleAlert,
  COMPLAINT_DRAFT_GENERATED: Bot,
  AUTHORITY_SELECTED: Building2,
  COMPLAINT_APPROVED: BadgeCheck,
  APPROVAL_WITHDRAWN: Undo2,
  SUBMISSION_ATTEMPTED: Send,
  SUBMISSION_ACCEPTED: MailCheck,
  SUBMISSION_FAILED: MailX,
  REPLY_RECEIVED: MessageSquareReply,
  REPLY_CLASSIFIED: Sparkles,
  REFERENCE_NUMBER_RECORDED: Hash,
  FOLLOWUP_SUGGESTED: BellRing,
  FOLLOWUP_APPROVED: BadgeCheck,
  FOLLOWUP_SENT: MailPlus,
  FOLLOWUP_FAILED: MailX,
  FOLLOWUP_DISMISSED: MailMinus,
  FOLLOWUPS_STOPPED: BellOff,
  ESCALATION_RECOMMENDED: ShieldAlert,
  RESOLUTION_EVIDENCE_UPLOADED: CameraIcon,
  RESOLUTION_ASSESSED: ScanSearch,
  RESOLUTION_CONFIRMED: CircleCheckBig,
  RESOLUTION_DISPUTED: CircleX,
  COMPLAINT_REOPENED: RotateCcw,
};

const ACTOR_LABELS: Record<ComplaintEvent["actor"], string> = {
  CITIZEN: "You",
  SYSTEM: "CivicPulse",
  AI: "AI assistant",
  AUTHORITY: "Department",
};

/** Events in chronological order, oldest first. */
export function ComplaintTimeline({ events }: { events: ComplaintEvent[] }) {
  return (
    <ol className="grid">
      {events.map((event, index) => {
        const Icon = EVENT_ICONS[event.event_type] ?? Circle;
        const isLast = index === events.length - 1;
        return (
          <li key={event.id} className="relative flex gap-3 pb-6 last:pb-0">
            {!isLast && (
              <span className="absolute top-9 bottom-0 left-[17px] w-px bg-border" aria-hidden />
            )}
            <span className="flex size-9 shrink-0 items-center justify-center rounded-full border border-border bg-card text-teal">
              <Icon className="size-4" aria-hidden />
            </span>
            <div className="grid gap-0.5 pt-1.5">
              <p className="text-sm font-medium text-foreground">{event.description}</p>
              <p className="text-xs text-muted-foreground">
                {ACTOR_LABELS[event.actor]} · <time dateTime={event.created_at}>{formatDateTime(event.created_at)}</time>
              </p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
