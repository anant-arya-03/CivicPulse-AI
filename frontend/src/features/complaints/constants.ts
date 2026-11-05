/**
 * Labels, icons, and colours for categories, severities, and statuses.
 * `Record<...>` types make TypeScript complain if a new backend value isn't listed here.
 */

import {
  Ban,
  CheckCircle2,
  CircleCheckBig,
  CircleDashed,
  CircleHelp,
  CloudRain,
  Construction,
  Droplets,
  FileClock,
  Hammer,
  Hourglass,
  Lightbulb,
  Loader,
  MailCheck,
  RotateCcw,
  Send,
  Trash2,
  Waves,
  type LucideIcon,
} from "lucide-react";

import type { Category, ComplaintStatus, Severity } from "@/types/api";

export const CATEGORY_META: Record<Category, { label: string; icon: LucideIcon }> = {
  ROAD_POTHOLE: { label: "Road pothole", icon: Construction },
  BROKEN_STREETLIGHT: { label: "Broken streetlight", icon: Lightbulb },
  GARBAGE_OVERFLOW: { label: "Overflowing garbage", icon: Trash2 },
  OPEN_DRAIN: { label: "Open drain", icon: Waves },
  WATER_LEAKAGE: { label: "Water leakage", icon: Droplets },
  WATERLOGGING: { label: "Waterlogging", icon: CloudRain },
  DAMAGED_INFRASTRUCTURE: { label: "Damaged public infrastructure", icon: Hammer },
  OTHER: { label: "Other", icon: CircleHelp },
};

export const CATEGORIES = Object.keys(CATEGORY_META) as [Category, ...Category[]];

export const SEVERITY_META: Record<Severity, { label: string; description: string }> = {
  LOW: { label: "Low", description: "An inconvenience, no immediate risk" },
  MEDIUM: { label: "Medium", description: "Should be fixed soon" },
  HIGH: { label: "High", description: "A risk to people's safety" },
  UNKNOWN: { label: "Not sure", description: "Let the department assess it" },
};

export const SEVERITIES = Object.keys(SEVERITY_META) as [Severity, ...Severity[]];

export type StatusTone = "slate" | "teal" | "navy" | "warning" | "success" | "error" | "outline";

export const STATUS_META: Record<
  ComplaintStatus,
  { label: string; tone: StatusTone; icon: LucideIcon; description: string }
> = {
  DRAFT: {
    label: "Draft",
    tone: "slate",
    icon: FileClock,
    description: "Saved, not sent to anyone yet.",
  },
  PENDING_REVIEW: {
    label: "Ready to send",
    tone: "slate",
    icon: CircleDashed,
    description: "You approved it. It hasn't been sent yet.",
  },
  SUBMITTED: {
    label: "Submitted",
    tone: "teal",
    icon: Send,
    description: "Submitted to the department. Waiting for a reply.",
  },
  ACKNOWLEDGED: {
    label: "Acknowledged",
    tone: "teal",
    icon: MailCheck,
    description: "The department confirmed it received the complaint.",
  },
  IN_PROGRESS: {
    label: "In progress",
    tone: "navy",
    icon: Loader,
    description: "The department says work is under way.",
  },
  RESOLVED_PENDING_VERIFICATION: {
    label: "Awaiting your verification",
    tone: "warning",
    icon: Hourglass,
    description: "The department says it's fixed. Please check and confirm.",
  },
  VERIFIED_RESOLVED: {
    label: "Verified resolved",
    tone: "success",
    icon: CircleCheckBig,
    description: "You confirmed the problem is fixed.",
  },
  CLOSED: {
    label: "Closed",
    tone: "success",
    icon: CheckCircle2,
    description: "This case is closed.",
  },
  REOPENED: {
    label: "Reopened",
    tone: "error",
    icon: RotateCcw,
    description: "The problem wasn't fixed, so the case was reopened.",
  },
  CANCELLED: {
    label: "Cancelled",
    tone: "outline",
    icon: Ban,
    description: "You cancelled this complaint.",
  },
};

export const STATUSES = Object.keys(STATUS_META) as [ComplaintStatus, ...ComplaintStatus[]];

export function categoryLabel(category: Category | null): string {
  return category ? CATEGORY_META[category].label : "Uncategorised";
}
