import { deliveryLabel, type DeliveryTone } from "@/features/complaints/submission";
import { cn } from "@/lib/utils";
import type { DeliveryStatus } from "@/types/api";

const TONES: Record<DeliveryTone, string> = {
  neutral: "bg-secondary text-slate-700",
  teal: "bg-teal-soft text-teal-strong",
  warning: "border border-dashed border-warning text-warning-strong",
  success: "bg-success-soft text-success",
  error: "bg-error-soft text-error-strong",
};

export function DeliveryBadge({ status, simulated = false }: { status: DeliveryStatus; simulated?: boolean }) {
  const { label, tone } = deliveryLabel(status, simulated);
  return (
    <span className={cn("inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium", TONES[tone])}>
      {label}
    </span>
  );
}
