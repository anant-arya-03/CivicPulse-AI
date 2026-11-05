import { CircleHelp } from "lucide-react";

import { CATEGORY_META } from "@/features/complaints/constants";
import { cn } from "@/lib/utils";
import type { Category } from "@/types/api";

export function CategoryLabel({ category, className }: { category: Category | null; className?: string }) {
  const meta = category ? CATEGORY_META[category] : null;
  const Icon = meta?.icon ?? CircleHelp;
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-sm text-muted-foreground", className)}>
      <Icon className="size-4 text-teal" aria-hidden />
      {meta?.label ?? "Uncategorised"}
    </span>
  );
}
