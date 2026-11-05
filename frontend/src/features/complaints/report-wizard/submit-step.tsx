"use client";

import { AlertTriangle, ArrowLeft, FlaskConical, Loader2, Paperclip, PencilLine, Send } from "lucide-react";
import { useState } from "react";

import { AuthorityCard } from "@/components/complaints/authority-card";
import { EvidenceImage } from "@/components/complaints/evidence-image";
import { ErrorState } from "@/components/shared/error-state";
import { FormAlert } from "@/components/shared/form-alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useApproveAndSend, useSubmissionPreview } from "@/features/complaints/hooks";
import { isApiError } from "@/lib/api-client";
import type { Complaint } from "@/types/api";

interface SubmitStepProps {
  complaint: Complaint;
  onGoTo: (step: number) => void;
  onSubmitted: () => void;
}

/** Step 6: the exact message that will be sent, explicit approval, then sending. */
export function SubmitStep({ complaint, onGoTo, onSubmitted }: SubmitStepProps) {
  const preview = useSubmissionPreview(complaint.id);
  const approveAndSend = useApproveAndSend(complaint.id);
  const [approved, setApproved] = useState(false);

  if (preview.isPending) {
    return (
      <div className="grid gap-3" aria-busy="true" aria-label="Preparing the preview">
        <Skeleton className="h-7 w-64" />
        <Skeleton className="h-72 rounded-xl" />
      </div>
    );
  }
  if (preview.isError) {
    return <ErrorState message="Couldn't load the preview." onRetry={() => preview.refetch()} />;
  }

  const data = preview.data;
  if (!data.ready || !data.authority || !data.content_sha256) {
    return (
      <div className="grid gap-4">
        <h2 className="text-xl font-semibold">Almost there</h2>
        <p className="text-sm text-muted-foreground">
          Before you can send this complaint, add {data.missing.join(", ")}.
        </p>
        <div className="flex flex-wrap gap-2">
          {data.missing.includes("a department") && (
            <Button variant="outline" onClick={() => onGoTo(4)}>Choose a department</Button>
          )}
          {data.missing.includes("a complaint letter") && (
            <Button variant="outline" onClick={() => onGoTo(5)}>Write the letter</Button>
          )}
          <Button variant="ghost" onClick={() => onGoTo(5)}>
            <ArrowLeft aria-hidden /> Back
          </Button>
        </div>
      </div>
    );
  }

  const pending = data.pending_communication;
  const lastAttemptFailed = pending?.delivery_status === "FAILED";
  const authority = data.authority;

  async function submit() {
    try {
      await approveAndSend.mutateAsync({
        contentSha256: data.content_sha256!,
        pendingId: pending && pending.delivery_status !== "SENDING" ? pending.id : undefined,
      });
      onSubmitted();
    } catch (error) {
      if (isApiError(error, 409)) void preview.refetch(); // something changed: show the latest
    }
  }

  const errorMessage = approveAndSend.isError
    ? isApiError(approveAndSend.error)
      ? approveAndSend.error.message
      : "Something went wrong. Please try again."
    : undefined;

  return (
    <div className="grid grid-cols-1 gap-6">
      <div className="grid gap-1">
        <h2 className="text-xl font-semibold">Check and send your complaint</h2>
        <p className="text-sm text-muted-foreground">
          This is exactly what will be sent. Nothing is sent until you approve it.
        </p>
      </div>

      {data.is_simulated && (
        <div role="note" className="flex items-start gap-3 rounded-xl border border-dashed border-warning bg-warning-soft p-4 text-sm">
          <FlaskConical className="mt-0.5 size-5 shrink-0 text-warning-strong" aria-hidden />
          <p className="text-warning-strong">
            <span className="font-semibold">Simulation mode.</span> This demo never emails a real
            department. Your complaint will be recorded as a <em>simulated</em> submission.
          </p>
        </div>
      )}

      <section aria-label="Message preview" className="grid gap-4 rounded-xl border border-border bg-background p-4">
        <div className="grid gap-2">
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">To</p>
            <Button variant="ghost" size="sm" onClick={() => onGoTo(4)}>
              <PencilLine aria-hidden /> Change
            </Button>
          </div>
          <AuthorityCard authority={authority} />
        </div>
        <p className="text-sm">
          <span className="text-muted-foreground">From:</span> {data.from_address}
        </p>
        <div className="grid gap-2">
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Message</p>
            <Button variant="ghost" size="sm" onClick={() => onGoTo(5)}>
              <PencilLine aria-hidden /> Edit letter
            </Button>
          </div>
          <p className="font-semibold text-navy">{data.subject}</p>
          <pre className="max-h-96 overflow-auto rounded-lg border border-border bg-card p-3 font-mono text-sm whitespace-pre-wrap">
            {data.body}
          </pre>
        </div>
        <div className="grid gap-2">
          <p className="flex items-center gap-1.5 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            <Paperclip className="size-3.5" aria-hidden /> Attached photos ({data.attachments.length})
          </p>
          <div className="flex flex-wrap gap-2">
            {data.attachments.map((photo, index) => (
              <EvidenceImage
                key={photo.evidence_id}
                src={photo.url}
                alt={`Attached photo ${index + 1}`}
                className="size-20 rounded-lg border border-border"
              />
            ))}
          </div>
        </div>
      </section>

      {lastAttemptFailed && !approveAndSend.isError && (
        <p role="alert" className="flex items-start gap-2 rounded-lg border border-error/30 bg-error-soft px-3 py-2 text-sm text-error-strong">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
          The last attempt to send failed, and nothing was delivered. You can try again.
        </p>
      )}
      <FormAlert message={errorMessage} />

      <div className="flex items-start gap-3 rounded-lg border border-border bg-card p-3">
        <Checkbox
          id="approve"
          checked={approved}
          onCheckedChange={(checked) => setApproved(checked === true)}
          className="mt-0.5"
        />
        <Label htmlFor="approve" className="leading-snug font-normal">
          I have reviewed this complaint and approve sending it to {authority.name}.
        </Label>
      </div>

      <div className="flex flex-wrap justify-between gap-3">
        <Button type="button" variant="outline" size="lg" onClick={() => onGoTo(5)}>
          <ArrowLeft aria-hidden /> Back
        </Button>
        <Button
          type="button"
          size="lg"
          disabled={!approved || approveAndSend.isPending}
          onClick={() => void submit()}
        >
          {approveAndSend.isPending ? <Loader2 className="animate-spin" aria-hidden /> : <Send aria-hidden />}
          {lastAttemptFailed || approveAndSend.isError ? "Try sending again" : "Approve and send"}
          {data.is_simulated && " (simulated)"}
        </Button>
      </div>
    </div>
  );
}
