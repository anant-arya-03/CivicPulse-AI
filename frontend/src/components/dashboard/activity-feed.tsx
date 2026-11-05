import { Activity } from "lucide-react";
import Link from "next/link";

import { formatRelative } from "@/lib/format";
import type { ActivityItem } from "@/types/api";

export function ActivityFeed({ items }: { items: ActivityItem[] }) {
  if (items.length === 0) {
    return <p className="text-sm text-muted-foreground">No activity yet.</p>;
  }
  return (
    <ol className="grid gap-4">
      {items.map((item) => (
        <li key={item.id} className="flex gap-3">
          <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full bg-teal-soft text-teal">
            <Activity className="size-4" aria-hidden />
          </span>
          <div className="grid min-w-0 gap-0.5">
            <p className="text-sm">{item.description}</p>
            <p className="truncate text-xs text-muted-foreground">
              <Link href={`/complaints/${item.complaint_id}`} className="hover:text-teal-strong hover:underline">
                {item.complaint_title ?? item.complaint_reference}
              </Link>{" "}
              · <time dateTime={item.created_at}>{formatRelative(item.created_at)}</time>
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}
