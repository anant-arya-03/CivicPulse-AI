"use client";

import { CameraIcon, CircleAlert, History, RefreshCw, ScanSearch } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { AiSourceBadge } from "@/components/complaints/ai-insight-panel";
import { EvidenceImage } from "@/components/complaints/evidence-image";
import { ErrorState } from "@/components/shared/error-state";
import { FormAlert } from "@/components/shared/form-alert";
import { ImageDropzone } from "@/components/shared/image-dropzone";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  useCheckRepair,
  useDecideRepair,
  useResolutionReviews,
  useRetryComparison,
} from "@/features/complaints/hooks";
import {
  ASSESSMENT_META,
  CONFIDENCE_LABEL,
  DECISION_META,
  canDispute,
  pendingReview,
} from "@/features/complaints/resolution";
import { ACCEPTED_PHOTO_TYPES, MAX_PHOTO_MB, validatePhotoFile } from "@/features/complaints/schemas";
import { isApiError } from "@/lib/api-client";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Complaint, ResolutionDecision, ResolutionReview } from "@/types/api";

const TONES = {
  success: "bg-success-soft text-success",
  warning: "bg-warning-soft text-warning-strong",
  error: "bg-error-soft text-error-strong",
  neutral: "bg-secondary text-slate-700",
};

function errorText(error: unknown) {
  return isApiError(error) ? error.message : "Something went wrong. Please try again.";
}

/** Checking a repair: "after" photo → the AI's comparison (advice) → the citizen decides. */
export function RepairCheck({ complaint }: { complaint: Complaint }) {
  const submitted = complaint.submitted_at !== null;
  const { data: reviews, isPending, isError, refetch } = useResolutionReviews(complaint.id, submitted);
  const canVerify = complaint.available_actions.includes("verify");
  if (!submitted || (!canVerify && !reviews?.length)) return null;

  const pending = pendingReview(reviews);
  const claimed = complaint.status === "RESOLVED_PENDING_VERIFICATION";
  const decided = (reviews ?? []).filter((r) => r.decision !== "PENDING");

  return (
    <Card id="check-repair" className={claimed ? "border-teal" : undefined}>
      <CardHeader>
        <CardTitle>
          <h2 className="flex items-center gap-2 text-base">
            <ScanSearch className="size-4 text-teal" aria-hidden /> Check the repair
          </h2>
        </CardTitle>
        <CardDescription>
          {claimed
            ? "The department says the problem is fixed. Take a new photo of the same place and compare it with your original photo. Only you decide."
            : canVerify
              ? "Fixed already? Add a photo taken after the repair to confirm it. Only you decide."
              : "Your earlier checks of this complaint."}
        </CardDescription>
      </CardHeader>
      <CardContent className="grid grid-cols-1 gap-4">
        {isPending ? (
          <div className="grid gap-3" aria-busy="true" aria-label="Loading your checks">
            <Skeleton className="h-40" />
          </div>
        ) : isError ? (
          <ErrorState message="Your checks couldn't be loaded." onRetry={() => refetch()} />
        ) : (
          <>
            {pending ? (
              <ReviewCard key={pending.id} review={pending} complaint={complaint} />
            ) : (
              canVerify && <AfterPhotoUpload complaintId={complaint.id} />
            )}
            {pending && canVerify && <AfterPhotoUpload complaintId={complaint.id} replacing />}
            {decided.length > 0 && <ResolutionHistory reviews={decided} />}
          </>
        )}
      </CardContent>
    </Card>
  );
}

// ── Upload the "after" photo, then compare ──────────────────────────────────

function AfterPhotoUpload({ complaintId, replacing = false }: { complaintId: string; replacing?: boolean }) {
  const check = useCheckRepair(complaintId);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(!replacing);

  function onFile(file: File) {
    const problem = validatePhotoFile(file);
    if (problem) {
      setError(problem);
      return;
    }
    setError(null);
    setProgress(0);
    check.mutate(
      { file, onProgress: setProgress },
      {
        onSuccess: () => setOpen(!replacing),
        onError: (err) => setError(errorText(err)),
        onSettled: () => setProgress(null),
      },
    );
  }

  if (!open) {
    return (
      <Button type="button" variant="outline" className="w-fit" onClick={() => setOpen(true)}>
        <CameraIcon aria-hidden /> Use a different photo instead
      </Button>
    );
  }

  const busy = check.isPending;
  return (
    <div className="grid gap-3">
      <ImageDropzone
        onFile={onFile}
        accept={ACCEPTED_PHOTO_TYPES.join(",")}
        hint={`A new photo of the same place, from a similar angle. JPEG, PNG or WebP, up to ${MAX_PHOTO_MB} MB.`}
        disabled={busy}
        error={error}
      />
      <div aria-live="polite" className="text-sm text-muted-foreground">
        {busy && progress !== null && progress < 100 && (
          <div className="grid gap-1">
            <span>Uploading… {progress}%</span>
            <Progress value={progress} aria-label="Upload progress" />
          </div>
        )}
        {busy && (progress === null || progress >= 100) && <span>Comparing the photos…</span>}
      </div>
    </div>
  );
}

// ── One check: before/after, the AI's opinion, the citizen's decision ───────

function ReviewCard({ review, complaint }: { review: ResolutionReview; complaint: Complaint }) {
  const retry = useRetryComparison(complaint.id);
  const a = review.assessment;
  return (
    <section aria-label="Before and after" className="grid grid-cols-1 gap-4 rounded-xl border border-border bg-background p-4">
      <BeforeAfter review={review} />

      <div className="grid gap-2 rounded-lg border border-border bg-card p-3">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-semibold text-navy">The AI thinks:</h3>
          {a ? (
            <>
              <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium", TONES[ASSESSMENT_META[a.assessment].tone])}>
                {ASSESSMENT_META[a.assessment].label}
              </span>
              <span className="text-xs text-muted-foreground">({CONFIDENCE_LABEL[a.confidence]})</span>
              <AiSourceBadge isMock={review.is_mock} />
            </>
          ) : (
            <span className="text-sm text-muted-foreground">No AI comparison</span>
          )}
        </div>
        {a && <p className="text-sm">{a.summary}</p>}
        {a && <Findings title="Changes it noticed" items={a.visible_changes} />}
        {a && <Findings title="Still visible" items={a.remaining_problems} />}
        {a && <Findings title="It can't tell" items={a.uncertainties} />}
        <ul className="grid gap-1" aria-label="Things to keep in mind">
          {review.cautions.map((note) => (
            <li key={note} className="flex items-start gap-2 text-sm text-warning-strong">
              <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
              {note}
            </li>
          ))}
        </ul>
        {review.ai_status === "FAILED" && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="w-fit"
            disabled={retry.isPending}
            onClick={() =>
              retry.mutate(review.followup_evidence.id, { onError: (error) => toast.error(errorText(error)) })
            }
          >
            <RefreshCw aria-hidden /> {retry.isPending ? "Comparing…" : "Try the AI again"}
          </Button>
        )}
      </div>

      <DecisionForm review={review} complaint={complaint} />
    </section>
  );
}

function BeforeAfter({ review, compact = false }: { review: ResolutionReview; compact?: boolean }) {
  const photos = [
    { label: "Before (your complaint)", photo: review.original_evidence },
    { label: `After (${formatDateTime(review.followup_evidence.created_at)})`, photo: review.followup_evidence },
  ];
  return (
    // History thumbnails stay side by side even on phones; the full comparison stacks.
    <div className={cn("grid gap-3", compact ? "grid-cols-2" : "grid-cols-1 sm:grid-cols-2")}>
      {photos.map(({ label, photo }) => (
        <figure key={label} className="grid gap-1">
          {photo ? (
            <EvidenceImage
              src={photo.url}
              alt={label}
              className={cn("w-full rounded-lg border border-border bg-muted object-cover", compact ? "aspect-[4/3] min-w-0" : "aspect-[4/3]")}
            />
          ) : (
            <div className="flex aspect-[4/3] items-center justify-center rounded-lg border border-dashed border-border text-sm text-muted-foreground">
              No photo
            </div>
          )}
          <figcaption className="text-xs text-muted-foreground">{label}</figcaption>
        </figure>
      ))}
    </div>
  );
}

function Findings({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <p className="text-xs font-medium text-muted-foreground">{title}</p>
      <ul className="list-disc pl-5 text-sm">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function DecisionForm({ review, complaint }: { review: ResolutionReview; complaint: Complaint }) {
  const decide = useDecideRepair();
  const [choice, setChoice] = useState<ResolutionDecision | null>(null);
  const [notes, setNotes] = useState("");
  const [checked, setChecked] = useState(false);
  const disputeAllowed = canDispute(complaint.status);
  const tooLong = notes.length > 1000;

  const options: { value: ResolutionDecision; label: string; hint: string; disabled: boolean }[] = [
    {
      value: "CONFIRMED_RESOLVED",
      label: "Yes, it's fixed",
      hint: "The complaint is marked as verified. Reminders stop.",
      disabled: false,
    },
    {
      value: "DISPUTED",
      label: "No, it's not fixed",
      hint: disputeAllowed
        ? "The complaint is reopened, and a message for the department is prepared for you to review."
        : "Available once the department reports a repair. Until then, we keep tracking the complaint.",
      disabled: !disputeAllowed,
    },
  ];

  return (
    <form
      method="post"
      className="grid gap-3"
      onSubmit={(event) => {
        event.preventDefault();
        if (!choice || !checked || tooLong) return;
        decide.mutate(
          { reviewId: review.id, decision: choice, notes },
          {
            onSuccess: (result) =>
              toast.success(
                result.decision === "CONFIRMED_RESOLVED"
                  ? "Thank you. The complaint is verified as resolved."
                  : "The complaint is reopened. Review the message for the department below.",
              ),
          },
        );
      }}
    >
      <fieldset className="grid gap-2">
        <legend className="mb-1 text-sm font-medium">Is the problem fixed?</legend>
        {options.map((option) => (
          <label
            key={option.value}
            className={cn(
              "flex items-start gap-3 rounded-lg border border-border p-3",
              option.disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer has-[:checked]:border-teal has-[:checked]:bg-teal-soft",
            )}
          >
            <input
              type="radio"
              name={`decision-${review.id}`}
              value={option.value}
              checked={choice === option.value}
              disabled={option.disabled}
              onChange={() => setChoice(option.value)}
              className="mt-1 size-4 accent-[var(--teal)]"
            />
            <span className="grid gap-0.5">
              <span className="text-sm font-medium">{option.label}</span>
              <span className="text-xs text-muted-foreground">{option.hint}</span>
            </span>
          </label>
        ))}
      </fieldset>

      <div className="grid gap-2">
        <Label htmlFor={`notes-${review.id}`}>What did you find? (optional)</Label>
        <Textarea
          id={`notes-${review.id}`}
          rows={3}
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          aria-invalid={tooLong || undefined}
          aria-describedby={`notes-${review.id}-hint`}
        />
        <p id={`notes-${review.id}-hint`} className={cn("text-xs", tooLong ? "text-error-strong" : "text-muted-foreground")}>
          {notes.length} / 1000 characters
          {choice === "DISPUTED" && " · Included in the message to the department (you can still edit it)."}
        </p>
      </div>

      <div className="flex items-start gap-3 rounded-lg border border-border bg-card p-3">
        <Checkbox
          id={`checked-${review.id}`}
          checked={checked}
          onCheckedChange={(value) => setChecked(value === true)}
          className="mt-0.5"
        />
        <Label htmlFor={`checked-${review.id}`} className="leading-snug font-normal">
          I checked the place myself. I understand the AI&apos;s opinion is only advice.
        </Label>
      </div>

      {decide.isError && <FormAlert message={errorText(decide.error)} />}
      <Button type="submit" className="w-fit" disabled={!choice || !checked || tooLong || decide.isPending}>
        {decide.isPending ? "Saving…" : "Save my decision"}
      </Button>
    </form>
  );
}

// ── The audit trail ─────────────────────────────────────────────────────────

function ResolutionHistory({ reviews }: { reviews: ResolutionReview[] }) {
  return (
    <section aria-labelledby="resolution-history-heading" className="grid gap-3">
      <h3 id="resolution-history-heading" className="flex items-center gap-2 text-sm font-semibold text-navy">
        <History className="size-4 text-muted-foreground" aria-hidden /> Earlier checks
      </h3>
      <ol className="grid gap-3">
        {reviews
          .slice()
          .reverse()
          .map((review) => {
            const meta = DECISION_META[review.decision];
            return (
              <li key={review.id} className="grid gap-2 rounded-lg border border-border p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium", TONES[meta.tone])}>{meta.label}</span>
                  <span className="text-xs text-muted-foreground">
                    {review.decided_at ? formatDateTime(review.decided_at) : formatDateTime(review.created_at)}
                    {review.assessment && ` · AI: ${ASSESSMENT_META[review.assessment.assessment].label.toLowerCase()}`}
                    {review.ai_status === "FAILED" && " · no AI comparison"}
                  </span>
                </div>
                <BeforeAfter review={review} compact />
                {review.citizen_notes && <p className="text-sm whitespace-pre-line">“{review.citizen_notes}”</p>}
              </li>
            );
          })}
      </ol>
    </section>
  );
}
