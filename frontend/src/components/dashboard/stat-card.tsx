import type { LucideIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: number | string;
  icon: LucideIcon;
  description?: string;
  /** Colour of the icon chip. */
  tone?: "teal" | "navy" | "warning" | "success";
}

const TONE_CLASSES: Record<NonNullable<StatCardProps["tone"]>, string> = {
  teal: "bg-teal-soft text-teal",
  navy: "bg-secondary text-navy",
  warning: "bg-warning-soft text-warning",
  success: "bg-success-soft text-success",
};

export function StatCard({ label, value, icon: Icon, description, tone = "teal" }: StatCardProps) {
  return (
    <Card>
      <CardContent className="flex flex-col-reverse items-start justify-between gap-3 sm:flex-row sm:gap-4">
        <div className="grid gap-1">
          <p className="text-sm leading-snug font-medium text-muted-foreground">{label}</p>
          <p className="text-2xl font-bold tracking-tight text-navy sm:text-3xl">{value}</p>
          {description && <p className="text-xs text-muted-foreground">{description}</p>}
        </div>
        <span
          className={cn("flex size-9 shrink-0 items-center justify-center rounded-lg sm:size-10", TONE_CLASSES[tone])}
        >
          <Icon className="size-5" aria-hidden />
        </span>
      </CardContent>
    </Card>
  );
}
