import { BadgeCheck, Building2, ExternalLink, FlaskConical, Mail, Phone } from "lucide-react";
import type { ReactNode } from "react";

import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Authority } from "@/types/api";

/** Always visible on fictional records, so a demo contact is never mistaken for a real one. */
export function DemoDirectoryBadge() {
  return (
    <span className="inline-flex shrink-0 items-center gap-1 rounded-full border border-dashed border-warning px-2 py-0.5 text-xs font-medium whitespace-nowrap text-warning-strong">
      <FlaskConical className="size-3" aria-hidden />
      Demo directory entry
    </span>
  );
}

/** Where the contact details come from: the official source and when it was checked. */
export function AuthoritySourceLine({ authority }: { authority: Authority }) {
  if (authority.is_demo) {
    return (
      <p className="text-xs text-warning-strong">
        Fictional department for demonstrations. Not a real government contact.
      </p>
    );
  }
  return (
    <p className="flex flex-wrap items-center gap-x-1.5 text-xs text-muted-foreground">
      <BadgeCheck className="size-3.5 text-success" aria-hidden />
      {authority.verified_at && <>Verified {formatDate(authority.verified_at)} from </>}
      {authority.source_url && (
        <a
          href={authority.source_url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-0.5 text-teal-strong hover:underline"
        >
          the official source <ExternalLink className="size-3" aria-hidden />
        </a>
      )}
    </p>
  );
}

interface AuthorityCardProps {
  authority: Authority;
  reasons?: string[];
  /** Rendered at the top right, e.g. a radio button or "Recommended". */
  action?: ReactNode;
  selected?: boolean;
  className?: string;
}

export function AuthorityCard({ authority, reasons, action, selected, className }: AuthorityCardProps) {
  return (
    <div
      className={cn(
        "grid gap-2 rounded-xl border bg-card p-4",
        selected ? "border-teal ring-2 ring-teal/30" : "border-border",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-secondary text-navy">
            <Building2 className="size-4.5" aria-hidden />
          </span>
          <div className="grid min-w-0 gap-1">
            <p className="font-semibold text-navy">{authority.name}</p>
            <p className="text-sm text-muted-foreground">{authority.jurisdiction}</p>
            {authority.is_demo && <DemoDirectoryBadge />}
          </div>
        </div>
        {action}
      </div>

      <div className="grid gap-1 pl-12 text-sm">
        {authority.official_email && (
          <p className="flex items-center gap-1.5 break-all">
            <Mail className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
            {authority.official_email}
          </p>
        )}
        {authority.official_phone && (
          <p className="flex items-center gap-1.5">
            <Phone className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
            {authority.official_phone}
          </p>
        )}
        <AuthoritySourceLine authority={authority} />
        {reasons && reasons.length > 0 && (
          <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs text-muted-foreground">
            {reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
