import { CalendarDays, ChevronRight, MapPin } from "lucide-react";
import Link from "next/link";

import { CategoryLabel } from "@/components/complaints/category-label";
import { EvidenceImage } from "@/components/complaints/evidence-image";
import { StatusBadge } from "@/components/complaints/status-badge";
import { formatDate } from "@/lib/format";
import type { ComplaintListItem } from "@/types/api";

export function ComplaintCard({ complaint }: { complaint: ComplaintListItem }) {
  const place = [complaint.locality, complaint.city].filter(Boolean).join(", ");
  const title = complaint.title ?? "Untitled draft";

  return (
    <Link
      href={`/complaints/${complaint.id}`}
      className="group flex gap-4 rounded-xl border border-border bg-card p-3 shadow-card transition-shadow hover:shadow-raised focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none sm:p-4"
    >
      <EvidenceImage
        src={complaint.thumbnail_url}
        alt={`Photo for ${title}`}
        className="size-20 shrink-0 rounded-lg sm:size-24"
      />
      <div className="grid min-w-0 flex-1 content-start gap-1.5">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={complaint.status} />
          <span className="text-xs text-muted-foreground">{complaint.public_reference}</span>
        </div>
        <h3 className="truncate text-base font-semibold group-hover:text-teal-strong">{title}</h3>
        <CategoryLabel category={complaint.category} />
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <CalendarDays className="size-3.5" aria-hidden />
            {formatDate(complaint.created_at)}
          </span>
          {place && (
            <span className="inline-flex min-w-0 items-center gap-1">
              <MapPin className="size-3.5 shrink-0" aria-hidden />
              <span className="truncate">{place}</span>
            </span>
          )}
        </div>
      </div>
      <ChevronRight
        className="hidden size-5 shrink-0 self-center text-muted-foreground group-hover:text-teal sm:block"
        aria-hidden
      />
      <span className="sr-only">View details</span>
    </Link>
  );
}
