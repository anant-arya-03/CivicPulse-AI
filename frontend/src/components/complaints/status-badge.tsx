import { STATUS_META, type StatusTone } from "@/features/complaints/constants";
import { cn } from "@/lib/utils";
import type { ComplaintStatus } from "@/types/api";

const TONE_CLASSES: Record<StatusTone, string> = {
  slate: "bg-secondary text-slate-700",
  teal: "bg-teal-soft text-teal-strong",
  navy: "bg-navy/10 text-navy",
  warning: "bg-warning-soft text-warning-strong",
  success: "bg-success-soft text-success",
  error: "bg-error-soft text-error-strong",
  outline: "border border-input text-muted-foreground",
};

/** Colour + icon + text, so the status never depends on colour alone. */
export function StatusBadge({ status, className }: { status: ComplaintStatus; className?: string }) {
  const { label, tone, icon: Icon } = STATUS_META[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap",
        TONE_CLASSES[tone],
        className,
      )}
    >
      <Icon className="size-3.5" aria-hidden />
      {label}
    </span>
  );
}
