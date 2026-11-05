"use client";

import {
  ArrowLeft,
  Building2,
  CalendarDays,
  CheckCircle2,
  FileWarning,
  Gauge,
  MapPin,
  MapPinCheck,
  PencilLine,
  RotateCcw,
  ScanSearch,
  Send,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import type { ReactNode } from "react";
import { toast } from "sonner";

import { AiInsightPanel } from "@/components/complaints/ai-insight-panel";
import { AuthorityCard } from "@/components/complaints/authority-card";
import { CategoryLabel } from "@/components/complaints/category-label";
import { ComplaintTimeline } from "@/components/complaints/complaint-timeline";
import { DeliveryBadge } from "@/components/complaints/delivery-badge";
import { EvidenceImage } from "@/components/complaints/evidence-image";
import { LocationMap } from "@/components/complaints/location-map-loader";
import { StatusBadge } from "@/components/complaints/status-badge";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { DemoTools } from "@/features/complaints/components/demo-tools";
import { RepairCheck } from "@/features/complaints/components/repair-check";
import { ResponseTracking } from "@/features/complaints/components/response-tracking";
import { SEVERITY_META, STATUS_META } from "@/features/complaints/constants";
import {
  useCancelComplaint,
  useCloseComplaint,
  useComplaint,
  useCommunications,
  useComplaintTimeline,
  useLatestAnalysis,
  useReopenComplaint,
} from "@/features/complaints/hooks";
import { REPLY_KIND_META } from "@/features/complaints/monitoring";
import { furthestAllowedStep } from "@/features/complaints/submission";
import { isApiError } from "@/lib/api-client";
import { formatDate, formatDateTime } from "@/lib/format";
import type { Communication, Complaint } from "@/types/api";

export function ComplaintDetailView() {
  const { id } = useParams<{ id: string }>();
  const { data: complaint, isPending, error, refetch } = useComplaint(id);

  if (isPending) return <DetailSkeleton />;
  if (error || !complaint) {
    // 422 means the id in the URL isn't even a valid id; for the user that's also "not found".
    return isApiError(error, 404) || isApiError(error, 422) ? (
      <EmptyState
        icon={FileWarning}
        title="Complaint not found"
        description="It doesn't exist, or it belongs to another account."
        action={
          <Button asChild>
            <Link href="/complaints">Back to my complaints</Link>
          </Button>
        }
      />
    ) : (
      <ErrorState
        message={isApiError(error) ? error.message : "Please try again."}
        onRetry={() => refetch()}
      />
    );
  }
  return <ComplaintDetail complaint={complaint} />;
}

function ComplaintDetail({ complaint }: { complaint: Complaint }) {
  const searchParams = useSearchParams();
  const justSaved = searchParams.get("saved") === "1";
  const justSubmitted = searchParams.get("submitted") === "1";
  const title = complaint.title ?? "Untitled draft";
  const photos = complaint.evidence.filter((e) => e.evidence_type === "ORIGINAL");

  return (
    <div className="grid gap-6">
      <Link
        href="/complaints"
        className="inline-flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-navy"
      >
        <ArrowLeft className="size-4" aria-hidden /> My complaints
      </Link>

      {justSaved && complaint.status === "DRAFT" && (
        <div
          role="status"
          className="flex items-start gap-3 rounded-xl border border-success/30 bg-success-soft p-4 text-sm"
        >
          <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-success" aria-hidden />
          <div>
            <p className="font-semibold text-navy">Your complaint is saved as a draft.</p>
            <p className="text-muted-foreground">
              Nothing has been sent to anyone. When you&apos;re ready, choose the department
              and review the message before sending it.
            </p>
          </div>
        </div>
      )}

      {justSubmitted && complaint.status === "SUBMITTED" && <SubmittedBanner complaint={complaint} />}

      <header className="grid gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={complaint.status} />
          <span className="text-sm text-muted-foreground">{complaint.public_reference}</span>
        </div>
        <h1 className="text-2xl font-bold sm:text-3xl">{title}</h1>
        <div className="flex flex-wrap gap-x-5 gap-y-1">
          <CategoryLabel category={complaint.category} />
          <span className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
            <CalendarDays className="size-4" aria-hidden /> Reported {formatDate(complaint.created_at)}
          </span>
          {complaint.severity && (
            <span className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
              <Gauge className="size-4" aria-hidden /> Severity: {SEVERITY_META[complaint.severity].label}
            </span>
          )}
        </div>
      </header>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="grid grid-cols-1 content-start gap-6">
          {/* A claimed repair is the most urgent thing to look at. */}
          {complaint.status === "RESOLVED_PENDING_VERIFICATION" && <RepairCheck complaint={complaint} />}
          <ResponseTracking complaint={complaint} />
          {complaint.status !== "RESOLVED_PENDING_VERIFICATION" && <RepairCheck complaint={complaint} />}
          <Section title="Photo evidence">
            {photos.length === 0 ? (
              <p className="text-sm text-muted-foreground">No photo has been added yet.</p>
            ) : (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {photos.map((photo, index) => (
                  <a
                    key={photo.id}
                    href={photo.url}
                    target="_blank"
                    rel="noreferrer"
                    className={index === 0 && photos.length > 1 ? "sm:col-span-2" : undefined}
                  >
                    <EvidenceImage
                      src={photo.url}
                      alt={`Photo ${index + 1} of ${title}`}
                      className="aspect-[4/3] w-full rounded-lg border border-border bg-muted"
                    />
                  </a>
                ))}
              </div>
            )}
          </Section>

          <Section title="Description">
            {complaint.description ? (
              <p className="text-sm whitespace-pre-line">{complaint.description}</p>
            ) : (
              <p className="text-sm text-muted-foreground">No description yet.</p>
            )}
            {complaint.observed_at && (
              <p className="mt-3 text-xs text-muted-foreground">
                Observed {formatDateTime(complaint.observed_at)}
              </p>
            )}
          </Section>

          <LocationSection complaint={complaint} />
          <AiAnalysisSection complaintId={complaint.id} />
          <LetterSection complaint={complaint} />
          <MessageHistory complaintId={complaint.id} />
          <TimelineSection complaintId={complaint.id} />
        </div>

        <aside aria-label="Status and department" className="grid content-start gap-6">
          <StatusCard complaint={complaint} />
          <Card>
            <CardHeader>
              <CardTitle>
                <h2 className="flex items-center gap-2 text-base">
                  <Building2 className="size-4 text-teal" aria-hidden /> Department
                </h2>
              </CardTitle>
              {!complaint.authority && (
                <CardDescription>Not selected yet. Choose it in step 4 of the report.</CardDescription>
              )}
            </CardHeader>
            {complaint.authority && (
              <CardContent>
                <AuthorityCard authority={complaint.authority} className="border-0 p-0" />
              </CardContent>
            )}
          </Card>
          <DemoTools complaint={complaint} />
        </aside>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2 className="text-base">{title}</h2>
        </CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function LocationSection({ complaint }: { complaint: Complaint }) {
  const lines = [
    complaint.address_line,
    [complaint.locality, complaint.city].filter(Boolean).join(", "),
    [complaint.state, complaint.postal_code, complaint.country].filter(Boolean).join(" "),
  ].filter(Boolean);
  const point =
    complaint.latitude !== null && complaint.longitude !== null
      ? { latitude: complaint.latitude, longitude: complaint.longitude }
      : null;

  return (
    <Section title="Location">
      {lines.length === 0 ? (
        <p className="text-sm text-muted-foreground">No location added yet.</p>
      ) : (
        <div className="grid gap-4">
          <div className="flex items-start gap-2">
            <MapPin className="mt-0.5 size-4 shrink-0 text-teal" aria-hidden />
            <address className="text-sm not-italic">
              {lines.map((line) => (
                <span key={line} className="block">
                  {line}
                </span>
              ))}
            </address>
          </div>
          {complaint.location_confirmed_at && (
            <p className="inline-flex items-center gap-1.5 text-xs text-success">
              <MapPinCheck className="size-3.5" aria-hidden /> Confirmed by you on{" "}
              {formatDate(complaint.location_confirmed_at)}
            </p>
          )}
          {point && (
            <div className="h-56 overflow-hidden rounded-lg border border-border">
              <LocationMap point={point} className="h-full w-full" />
            </div>
          )}
        </div>
      )}
    </Section>
  );
}

function AiAnalysisSection({ complaintId }: { complaintId: string }) {
  const { data: analysis } = useLatestAnalysis(complaintId);
  if (!analysis) return null; // no successful analysis: nothing to show
  return (
    <section aria-label="AI analysis">
      <AiInsightPanel state={{ kind: "ready", analysis }} />
    </section>
  );
}

function LetterSection({ complaint }: { complaint: Complaint }) {
  if (!complaint.draft_body) return null;
  return (
    <Section title="Complaint letter">
      <p className="text-sm font-semibold text-navy">{complaint.draft_subject}</p>
      <p className="mt-3 rounded-lg border border-border bg-background p-4 font-mono text-sm whitespace-pre-wrap">
        {complaint.draft_body}
      </p>
      {(complaint.status === "DRAFT" || complaint.status === "PENDING_REVIEW") && (
        <p className="mt-3 text-xs text-muted-foreground">Not sent yet.</p>
      )}
    </Section>
  );
}

function SubmittedBanner({ complaint }: { complaint: Complaint }) {
  return (
    <div role="status" className="grid gap-2 rounded-xl border border-dashed border-warning bg-warning-soft p-4 text-sm">
      <p className="flex items-center gap-2 font-semibold text-navy">
        <CheckCircle2 className="size-5 text-success" aria-hidden />
        Simulated submission complete
      </p>
      <p className="text-warning-strong">
        No email was sent to a real department. This demo records what would have been sent.
      </p>
      <dl className="grid gap-x-6 gap-y-1 sm:grid-cols-3">
        <div>
          <dt className="text-muted-foreground">Complaint ID</dt>
          <dd className="font-medium">{complaint.public_reference}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Department</dt>
          <dd className="font-medium">{complaint.authority?.name ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Submitted</dt>
          <dd className="font-medium">{complaint.submitted_at ? formatDateTime(complaint.submitted_at) : "—"}</dd>
        </div>
      </dl>
      <p className="text-muted-foreground">
        Next: CivicPulse watches for the department&apos;s reply. If it doesn&apos;t answer by the
        deadline, you&apos;ll be offered a reminder to review. Nothing is sent without your approval.
      </p>
    </div>
  );
}

function messageTitle(message: Communication) {
  if (message.communication_type === "REPLY") return `Reply from ${message.sender ?? "the department"}`;
  if (message.communication_type === "FOLLOW_UP") {
    const what = message.followup_number ? `Reminder ${message.followup_number}` : "\"Not fixed\" message";
    return `${what} to ${message.recipient}`;
  }
  return `Complaint to ${message.recipient}`;
}

function messageDate(message: Communication) {
  if (message.received_at) return `Received ${formatDateTime(message.received_at)}`;
  if (message.sent_at) return `Sent ${formatDateTime(message.sent_at)}`;
  if (message.delivery_status === "DRAFT") return `Drafted ${formatDateTime(message.created_at)}`;
  return `Created ${formatDateTime(message.created_at)}`;
}

/** Every message to and from the department, oldest first. */
function MessageHistory({ complaintId }: { complaintId: string }) {
  const { data: messages } = useCommunications(complaintId);
  if (!messages || messages.length === 0) return null;
  return (
    <Section title="Messages">
      <ol className="grid gap-3">
        {messages.map((message) => (
          <li
            key={message.id}
            className={
              message.direction === "INBOUND"
                ? "rounded-lg border border-teal/30 bg-teal-soft/40 p-3"
                : "rounded-lg border border-border p-3"
            }
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-medium">{messageTitle(message)}</p>
              <DeliveryBadge status={message.delivery_status} simulated={message.is_simulated} />
            </div>
            <p className="mt-1 text-sm text-navy">{message.subject}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              {messageDate(message)}
              {message.attempt_count > 1 && ` · ${message.attempt_count} attempts`}
              {message.attachments.length > 0 && ` · ${message.attachments.length} photo(s)`}
            </p>
            {message.reply_kind && (
              <p className="mt-1 text-xs">
                <span className="font-medium">{REPLY_KIND_META[message.reply_kind].label}</span>
                <span className="text-muted-foreground">
                  {message.reply_kind_source === "CITIZEN" ? " (marked by you)" : " (read by AI)"}
                  {message.reference_number && ` · reference ${message.reference_number}`}
                </span>
              </p>
            )}
            {message.error_message && message.delivery_status === "FAILED" && (
              <p className="mt-1 text-xs text-error-strong">{message.error_message}</p>
            )}
            <details className="mt-2 text-sm">
              <summary className="cursor-pointer text-teal-strong">Show message</summary>
              <pre className="mt-2 rounded-lg bg-background p-3 font-mono text-xs whitespace-pre-wrap">{message.body}</pre>
            </details>
          </li>
        ))}
      </ol>
    </Section>
  );
}

function TimelineSection({ complaintId }: { complaintId: string }) {
  const { data: events, isPending, isError, refetch } = useComplaintTimeline(complaintId);
  return (
    <Section title="Timeline">
      {isPending ? (
        <div className="grid gap-3">
          <Skeleton className="h-10" />
          <Skeleton className="h-10" />
        </div>
      ) : isError ? (
        <ErrorState message="The timeline couldn't be loaded." onRetry={() => refetch()} />
      ) : (
        <ComplaintTimeline events={events} />
      )}
    </Section>
  );
}

function StatusCard({ complaint }: { complaint: Complaint }) {
  const cancel = useCancelComplaint(complaint.id);
  const close = useCloseComplaint(complaint.id);
  const reopen = useReopenComplaint(complaint.id);
  const actions = complaint.available_actions;
  const canEdit = actions.includes("edit");
  // Reopen the wizard at the furthest step this draft can be on.
  const editStep = furthestAllowedStep(complaint);
  const canSend = actions.includes("submit");

  function run(mutation: typeof cancel, success: string) {
    mutation.mutate(undefined, {
      onSuccess: () => toast.success(success),
      onError: (error) =>
        toast.error(isApiError(error) ? error.message : "Something went wrong. Please try again."),
    });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2 className="text-base">Status</h2>
        </CardTitle>
        <CardDescription>{STATUS_META[complaint.status].description}</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-2">
        {canSend && (
          <Button asChild className="w-full">
            <Link href={`/report?draft=${complaint.id}&step=6`}>
              <Send aria-hidden /> Review and send
            </Link>
          </Button>
        )}
        {canEdit && (
          <Button asChild variant={canSend ? "outline" : "default"} className="w-full">
            <Link href={`/report?draft=${complaint.id}&step=${editStep}`}>
              <PencilLine aria-hidden /> Continue editing
            </Link>
          </Button>
        )}
        {actions.includes("verify") && complaint.status === "RESOLVED_PENDING_VERIFICATION" && (
          <Button asChild className="w-full">
            <a href="#check-repair">
              <ScanSearch aria-hidden /> Check the repair
            </a>
          </Button>
        )}
        {actions.includes("reopen") && (
          <ConfirmDialog
            trigger={
              <Button variant="outline" className="w-full" disabled={reopen.isPending}>
                <RotateCcw aria-hidden /> Reopen complaint
              </Button>
            }
            title="Has the problem come back?"
            description="Reopen only if you have checked the place yourself. A message for the department will be prepared for you to review; nothing is sent until you approve it."
            confirmLabel="Yes, reopen it"
            onConfirm={() =>
              reopen.mutate("", {
                onSuccess: () => toast.success("Complaint reopened. Review the message for the department."),
                onError: (error) =>
                  toast.error(isApiError(error) ? error.message : "Something went wrong. Please try again."),
              })
            }
          />
        )}
        {actions.includes("close") && (
          <ConfirmDialog
            trigger={
              <Button variant="outline" className="w-full" disabled={close.isPending}>
                <CheckCircle2 aria-hidden /> Close complaint
              </Button>
            }
            title="Close this complaint?"
            description="Closing marks the case as finished. You can reopen it later if the problem comes back."
            confirmLabel="Close complaint"
            onConfirm={() => run(close, "Complaint closed.")}
          />
        )}
        {actions.includes("cancel") && (
          <ConfirmDialog
            trigger={
              <Button variant="destructive" className="w-full" disabled={cancel.isPending}>
                <XCircle aria-hidden /> Cancel complaint
              </Button>
            }
            title="Cancel this complaint?"
            description="A cancelled complaint can't be edited or submitted again. It stays in your list for your records."
            confirmLabel="Cancel complaint"
            onConfirm={() => run(cancel, "Complaint cancelled.")}
          />
        )}
        {actions.length === 0 && (
          <p className="text-sm text-muted-foreground">There&apos;s nothing more to do on this complaint.</p>
        )}
      </CardContent>
    </Card>
  );
}

function DetailSkeleton() {
  return (
    <div className="grid gap-6" aria-busy="true" aria-label="Loading complaint">
      <Skeleton className="h-5 w-32" />
      <Skeleton className="h-9 w-2/3" />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <Skeleton className="h-96 rounded-xl" />
        <Skeleton className="h-48 rounded-xl" />
      </div>
    </div>
  );
}
