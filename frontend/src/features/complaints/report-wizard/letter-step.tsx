"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { AlertTriangle, ArrowLeft, FileText, Loader2, RefreshCw, Save } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";

import { AiSourceBadge } from "@/components/complaints/ai-insight-panel";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { FormAlert } from "@/components/shared/form-alert";
import { FormField, fieldAria } from "@/components/shared/form-field";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useDraftLetter, useUpdateComplaint } from "@/features/complaints/hooks";
import { letterSchema, type LetterValues } from "@/features/complaints/schemas";
import { isApiError } from "@/lib/api-client";
import type { Complaint, ComplaintDraftResponse } from "@/types/api";

interface LetterStepProps {
  complaint: Complaint;
  onBack: () => void;
  onSaved: () => void;
}

/**
 * Step 5: the formal complaint letter.
 *
 * The AI writes the wording; the facts (reference, address, photos…) are filled in by the
 * backend. The citizen edits freely. Nothing is sent anywhere: submission arrives later.
 */
export function LetterStep({ complaint, onBack, onSaved }: LetterStepProps) {
  const draftLetter = useDraftLetter(complaint.id);
  const updateComplaint = useUpdateComplaint(complaint.id);
  const [source, setSource] = useState<ComplaintDraftResponse | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LetterValues>({
    resolver: zodResolver(letterSchema),
    defaultValues: { subject: complaint.draft_subject ?? "", body: complaint.draft_body ?? "" },
  });
  const hasLetter = Boolean(complaint.draft_body) || source !== null;

  async function generate(mode: "ai" | "template", replaceExisting: boolean) {
    try {
      const result = await draftLetter.mutateAsync({ mode, replace_existing: replaceExisting });
      setSource(result);
      reset({ subject: result.draft_subject, body: result.draft_body });
    } catch {
      // The error is shown from draftLetter.error below.
    }
  }

  // Draft the letter automatically the first time this step opens.
  const autoStarted = useRef(false);
  useEffect(() => {
    if (autoStarted.current || complaint.draft_body) return;
    autoStarted.current = true;
    void generate("ai", false);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once on first open
  }, []);

  async function onSubmit(values: LetterValues) {
    try {
      await updateComplaint.mutateAsync({ draft_subject: values.subject, draft_body: values.body });
      onSaved();
    } catch (error) {
      setError("root", {
        message: isApiError(error) ? error.message : "Couldn't save the letter. Please try again.",
      });
    }
  }

  const failed = draftLetter.isError && !hasLetter;
  const busy = draftLetter.isPending;

  return (
    <div className="grid grid-cols-1 gap-6">
      <div className="grid gap-1">
        <h2 className="text-xl font-semibold">Review your complaint letter</h2>
        <p className="text-sm text-muted-foreground">
          This is the formal complaint for the department. Edit it however you like. Nothing is
          sent until you approve it in the last step.
        </p>
      </div>

      {busy && !hasLetter && (
        <p role="status" className="flex items-center gap-2 rounded-xl border border-teal/30 bg-teal-soft/40 p-4 text-sm font-medium text-teal-strong">
          <Loader2 className="size-4 animate-spin" aria-hidden />
          Writing your complaint letter…
        </p>
      )}

      {failed && (
        <div role="alert" className="grid gap-3 rounded-xl border border-warning/40 bg-warning-soft p-4">
          <p className="flex items-start gap-2 text-sm text-warning-strong">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
            {isApiError(draftLetter.error)
              ? draftLetter.error.message
              : "The AI couldn't write the letter right now."}
          </p>
          <div className="flex flex-wrap gap-2">
            <Button type="button" onClick={() => void generate("template", false)}>
              <FileText aria-hidden /> Use a basic template
            </Button>
            <Button type="button" variant="outline" onClick={() => void generate("ai", false)}>
              <RefreshCw aria-hidden /> Try the AI again
            </Button>
          </div>
        </div>
      )}

      {hasLetter && (
        <form onSubmit={handleSubmit(onSubmit)} noValidate className="grid grid-cols-1 gap-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              {source?.source === "ai" ? (
                <>
                  <AiSourceBadge isMock={source.is_mock} /> Drafted by AI. Please read it carefully.
                </>
              ) : source?.source === "template" ? (
                "Created from the standard template."
              ) : (
                "Your saved letter."
              )}
            </p>
            <ConfirmDialog
              trigger={
                <Button type="button" variant="ghost" size="sm" disabled={busy}>
                  {busy ? <Loader2 className="animate-spin" aria-hidden /> : <RefreshCw aria-hidden />}
                  Write it again with AI
                </Button>
              }
              title="Replace your letter?"
              description="The AI will write a new letter. Any changes you made to the current one will be lost."
              confirmLabel="Replace letter"
              cancelLabel="Keep my letter"
              onConfirm={() => void generate("ai", true)}
            />
          </div>

          <FormAlert
            message={
              errors.root?.message ??
              (draftLetter.isError && isApiError(draftLetter.error) ? draftLetter.error.message : undefined)
            }
          />

          <FormField id="subject" label="Subject" error={errors.subject?.message}>
            <Input {...fieldAria("subject", errors.subject?.message)} {...register("subject")} />
          </FormField>

          <FormField id="body" label="Letter" error={errors.body?.message}>
            <Textarea
              rows={18}
              className="font-mono text-sm leading-relaxed"
              {...fieldAria("body", errors.body?.message)}
              {...register("body")}
            />
          </FormField>

          <div className="flex justify-between gap-3">
            <Button type="button" variant="outline" size="lg" onClick={onBack}>
              <ArrowLeft aria-hidden /> Back
            </Button>
            <Button type="submit" size="lg" disabled={isSubmitting || busy}>
              {isSubmitting ? <Loader2 className="animate-spin" aria-hidden /> : <Save aria-hidden />}
              {complaint.authority ? "Save and continue" : "Save complaint"}
            </Button>
          </div>
        </form>
      )}

      {!hasLetter && !busy && !failed && (
        <Button type="button" variant="outline" onClick={onBack} className="w-fit">
          <ArrowLeft aria-hidden /> Back
        </Button>
      )}
    </div>
  );
}
