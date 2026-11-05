"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { BellRing, CalendarClock, Hash, Info, MessageSquareReply, PencilLine, Send, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { AuthorityCard } from "@/components/complaints/authority-card";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { ErrorState } from "@/components/shared/error-state";
import { FormAlert } from "@/components/shared/form-alert";
import { FormField, fieldAria } from "@/components/shared/form-field";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  useApproveAndSendFollowup,
  useDismissFollowup,
  useMonitoring,
  useSetReplyKind,
  useUpdateFollowup,
} from "@/features/complaints/hooks";
import {
  REPLY_KIND_CHOICES,
  REPLY_KIND_META,
  deadlineSentence,
  reminderCount,
} from "@/features/complaints/monitoring";
import { reminderSchema, type ReminderValues } from "@/features/complaints/schemas";
import { isApiError } from "@/lib/api-client";
import { formatDateTime } from "@/lib/format";
import type { Communication, Complaint, MonitoringState, ReplyKind } from "@/types/api";

function errorText(error: unknown) {
  return isApiError(error) ? error.message : "Something went wrong. Please try again.";
}

/** Replies, deadlines, reminders and escalation for a submitted complaint. */
export function ResponseTracking({ complaint }: { complaint: Complaint }) {
  const submitted = complaint.submitted_at !== null;
  const { data: state, isPending, isError, refetch } = useMonitoring(complaint.id, submitted);
  if (!submitted) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2 className="flex items-center gap-2 text-base">
            <BellRing className="size-4 text-teal" aria-hidden /> Response tracking
          </h2>
        </CardTitle>
        <CardDescription>
          CivicPulse watches for the department&apos;s reply. Reminders are only suggested, and
          nothing is sent without your approval.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        {isPending ? (
          <div className="grid gap-3" aria-busy="true" aria-label="Loading response tracking">
            <Skeleton className="h-5 w-2/3" />
            <Skeleton className="h-16" />
          </div>
        ) : isError ? (
          <ErrorState message="Response tracking couldn't be loaded." onRetry={() => refetch()} />
        ) : (
          <TrackingBody complaint={complaint} state={state} />
        )}
      </CardContent>
    </Card>
  );
}

function TrackingBody({ complaint, state }: { complaint: Complaint; state: MonitoringState }) {
  const deadline = deadlineSentence(state);
  const latest = state.latest_reply;
  return (
    <>
      <dl className="grid gap-3 text-sm sm:grid-cols-2">
        <div>
          <dt className="flex items-center gap-2 text-muted-foreground">
            <Hash className="size-4 shrink-0" aria-hidden /> Department&apos;s reference
          </dt>
          <dd className="pl-6 font-medium">{state.authority_reference_number ?? "Not received yet"}</dd>
        </div>
        <div>
          <dt className="flex items-center gap-2 text-muted-foreground">
            <Send className="size-4 shrink-0" aria-hidden /> Reminders
          </dt>
          <dd className="pl-6 font-medium">{reminderCount(state)}</dd>
        </div>
      </dl>

      {deadline && state.monitored && (
        <p className="flex items-start gap-2 rounded-lg bg-muted px-3 py-2 text-sm">
          <CalendarClock className="mt-0.5 size-4 shrink-0 text-teal" aria-hidden />
          <span>{deadline}</span>
        </p>
      )}

      {complaint.status === "RESOLVED_PENDING_VERIFICATION" && (
        <p role="status" className="flex items-start gap-2 rounded-lg border border-teal/30 bg-teal-soft px-3 py-2 text-sm">
          <Info className="mt-0.5 size-4 shrink-0 text-teal-strong" aria-hidden />
          <span>
            The department says the issue is fixed. Reminders have stopped. Only you can confirm
            it is really fixed: use <a href="#check-repair" className="font-medium text-teal-strong underline">Check the repair</a>.
          </span>
        </p>
      )}

      {latest?.reply_kind === "REQUEST_FOR_INFO" && state.monitored && (
        <p role="status" className="flex items-start gap-2 rounded-lg border border-warning/40 bg-warning-soft px-3 py-2 text-sm">
          <Info className="mt-0.5 size-4 shrink-0 text-warning-strong" aria-hidden />
          <span>
            The department asked for more information. Reminders are paused. Please reply to
            the department directly with the details they asked for.
          </span>
        </p>
      )}

      {state.replies_to_review.map((reply) => (
        <ReplyReview key={reply.id} reply={reply} />
      ))}

      {state.open_followup && state.open_followup_sha256 && (
        <FollowupCard
          // A new key resets the form whenever the saved text changes.
          key={`${state.open_followup.id}:${state.open_followup_sha256}`}
          message={state.open_followup}
          contentSha256={state.open_followup_sha256}
        />
      )}

      {state.escalation && <EscalationCard escalation={state.escalation} />}
    </>
  );
}

// ── A suggested reminder: review, edit, approve and send, or dismiss ────────

function FollowupCard({ message, contentSha256 }: { message: Communication; contentSha256: string }) {
  const [editing, setEditing] = useState(false);
  const [approved, setApproved] = useState(false);
  const save = useUpdateFollowup();
  const approveAndSend = useApproveAndSendFollowup();
  const dismiss = useDismissFollowup();
  const failed = message.delivery_status === "FAILED";
  const sending = message.delivery_status === "SENDING" || approveAndSend.isPending;
  // A numbered reminder, or (no number) the message saying a claimed repair isn't done.
  const name = message.followup_number ? `Reminder ${message.followup_number}` : "Message: not fixed";

  function sendIt() {
    approveAndSend.mutate(
      {
        id: message.id,
        contentSha256,
        alreadyApproved: message.delivery_status !== "DRAFT",
      },
      {
        onSuccess: () => toast.success(`${name} sent${message.is_simulated ? " (simulated)" : ""}.`),
        onError: (error) => toast.error(errorText(error)),
      },
    );
  }

  return (
    <section aria-label={name} className="grid gap-3 rounded-xl border border-warning/50 bg-background p-4">
      <div className="grid gap-1">
        <h3 className="font-semibold text-navy">
          {message.followup_number
            ? `Reminder ${message.followup_number} is ready for you`
            : "A message telling the department it isn't fixed"}
        </h3>
        <p className="text-sm text-muted-foreground">
          {message.followup_number
            ? "The department hasn't answered by the deadline. Check this reminder and edit it if you like."
            : "You found that the problem isn't fixed. Check this message and edit it if you like."}{" "}
          Nothing is sent unless you approve it.
        </p>
      </div>

      {message.is_simulated && (
        <p className="rounded-lg border border-dashed border-warning bg-warning-soft px-3 py-2 text-sm text-warning-strong">
          Demo mode: sending is simulated. No email will reach a real department.
        </p>
      )}

      <p className="text-sm">
        <span className="text-muted-foreground">To </span>
        <span className="font-medium">{message.recipient}</span>
      </p>

      {editing ? (
        <ReminderForm message={message} onDone={() => setEditing(false)} save={save} />
      ) : (
        <div className="grid gap-2">
          <p className="text-sm font-semibold text-navy">{message.subject}</p>
          {/* tabIndex: a scrollable box must be reachable with the keyboard. */}
          <pre
            tabIndex={0}
            aria-label="Message text"
            className="max-h-80 overflow-auto rounded-lg border border-border bg-muted/40 p-3 font-mono text-xs whitespace-pre-wrap focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            {message.body}
          </pre>
          <Button type="button" variant="outline" size="sm" className="w-fit" onClick={() => setEditing(true)}>
            <PencilLine aria-hidden /> Edit reminder
          </Button>
        </div>
      )}

      {failed && (
        <FormAlert message={`The last attempt failed and nothing was delivered. ${message.error_message ?? ""}`.trim()} />
      )}
      {approveAndSend.isError && !failed && <FormAlert message={errorText(approveAndSend.error)} />}

      {!editing && (
        <>
          <div className="flex items-start gap-3 rounded-lg border border-border bg-card p-3">
            <Checkbox
              id={`approve-${message.id}`}
              checked={approved}
              onCheckedChange={(checked) => setApproved(checked === true)}
              className="mt-0.5"
            />
            <Label htmlFor={`approve-${message.id}`} className="leading-snug font-normal">
              I have reviewed this {message.followup_number ? "reminder" : "message"} and approve
              sending it to {message.recipient}.
            </Label>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="button" onClick={sendIt} disabled={!approved || sending}>
              <Send aria-hidden />
              {failed ? "Try sending again" : `Approve and send ${message.followup_number ? "reminder" : "message"}`}
              {message.is_simulated && " (simulated)"}
            </Button>
            <ConfirmDialog
              trigger={
                <Button type="button" variant="ghost" disabled={sending || dismiss.isPending}>
                  Don&apos;t send it
                </Button>
              }
              title="Don't send this reminder?"
              description="Nothing will be sent. CivicPulse will check again after another waiting period."
              confirmLabel="Don't send"
              onConfirm={() =>
                dismiss.mutate(message.id, {
                  onSuccess: () => toast.success("Reminder dismissed. Nothing was sent."),
                  onError: (error) => toast.error(errorText(error)),
                })
              }
            />
          </div>
        </>
      )}
    </section>
  );
}

function ReminderForm({
  message,
  onDone,
  save,
}: {
  message: Communication;
  onDone: () => void;
  save: ReturnType<typeof useUpdateFollowup>;
}) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ReminderValues>({
    resolver: zodResolver(reminderSchema),
    defaultValues: { subject: message.subject, body: message.body },
  });

  const onSubmit = handleSubmit((values) =>
    save.mutate(
      { id: message.id, ...values },
      {
        onSuccess: () => {
          toast.success("Reminder saved. Please review and approve it.");
          onDone();
        },
      },
    ),
  );

  const subjectId = `reminder-subject-${message.id}`;
  const bodyId = `reminder-body-${message.id}`;
  return (
    <form method="post" onSubmit={onSubmit} className="grid gap-3" noValidate>
      <FormField id={subjectId} label="Subject" error={errors.subject?.message}>
        <Input {...fieldAria(subjectId, errors.subject?.message)} {...register("subject")} />
      </FormField>
      <FormField id={bodyId} label="Reminder" error={errors.body?.message}>
        <Textarea rows={12} className="font-mono text-sm" {...fieldAria(bodyId, errors.body?.message)} {...register("body")} />
      </FormField>
      {save.isError && <FormAlert message={errorText(save.error)} />}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={save.isPending}>
          Save reminder
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

// ── A reply the citizen must interpret (AI unavailable or unsure) ───────────

function ReplyReview({ reply }: { reply: Communication }) {
  const [choice, setChoice] = useState<ReplyKind | null>(null);
  const setKind = useSetReplyKind();

  return (
    <section aria-label="Reply to review" className="grid gap-3 rounded-xl border border-warning/50 bg-background p-4">
      <div className="grid gap-1">
        <h3 className="flex items-center gap-2 font-semibold text-navy">
          <MessageSquareReply className="size-4 text-teal" aria-hidden /> What does this reply mean?
        </h3>
        <p className="text-sm text-muted-foreground">
          {reply.reply_summary
            ? "The AI wasn't sure about this reply, so please choose."
            : "The AI couldn't read this reply, so please choose."}{" "}
          Your choice decides what happens next.
        </p>
      </div>
      <figure className="grid gap-1">
        <figcaption className="text-xs text-muted-foreground">
          From {reply.sender ?? "the department"}
          {reply.received_at && `, ${formatDateTime(reply.received_at)}`}
        </figcaption>
        <pre
          tabIndex={0}
          aria-label="Reply text"
          className="max-h-60 overflow-auto rounded-lg border border-border bg-muted/40 p-3 font-mono text-xs whitespace-pre-wrap focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          {reply.body}
        </pre>
      </figure>
      <fieldset className="grid gap-2">
        <legend className="mb-1 text-sm font-medium">The department&apos;s reply…</legend>
        {REPLY_KIND_CHOICES.map((kind) => (
          <label key={kind} className="flex cursor-pointer items-start gap-3 rounded-lg border border-border p-3 has-[:checked]:border-teal has-[:checked]:bg-teal-soft">
            <input
              type="radio"
              name={`reply-kind-${reply.id}`}
              value={kind}
              checked={choice === kind}
              onChange={() => setChoice(kind)}
              className="mt-1 size-4 accent-[var(--teal)]"
            />
            <span className="grid gap-0.5">
              <span className="text-sm font-medium">{REPLY_KIND_META[kind].label}</span>
              <span className="text-xs text-muted-foreground">{REPLY_KIND_META[kind].effect}</span>
            </span>
          </label>
        ))}
      </fieldset>
      {setKind.isError && <FormAlert message={errorText(setKind.error)} />}
      <Button
        type="button"
        className="w-fit"
        disabled={!choice || setKind.isPending}
        onClick={() =>
          choice &&
          setKind.mutate(
            { id: reply.id, kind: choice },
            { onSuccess: () => toast.success("Saved. Thank you.") },
          )
        }
      >
        Save meaning
      </Button>
    </section>
  );
}

// ── Escalation: verified contacts only, never contacted for the citizen ─────

function EscalationCard({ escalation }: { escalation: NonNullable<MonitoringState["escalation"]> }) {
  return (
    <section aria-label="Escalation" className="grid gap-3 rounded-xl border border-error/30 bg-error-soft/40 p-4">
      <h3 className="flex items-center gap-2 font-semibold text-navy">
        <ShieldAlert className="size-4 text-error-strong" aria-hidden /> Escalation suggested
      </h3>
      <p className="text-sm">{escalation.reason}</p>
      {escalation.contacts.length > 0 ? (
        <ul className="grid gap-3">
          {escalation.contacts.map((contact) => (
            <li key={contact.id}>
              <AuthorityCard authority={contact} />
              {!contact.official_phone && (
                <p className="mt-1 text-xs text-muted-foreground">
                  No phone number is listed for this office in the directory.
                </p>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">
          The directory has no higher office for this department. We never guess contact details.
        </p>
      )}
      <p className="flex items-start gap-2 text-xs text-muted-foreground">
        <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
        CivicPulse never contacts these offices for you. Contact them yourself if you decide to.
      </p>
    </section>
  );
}
