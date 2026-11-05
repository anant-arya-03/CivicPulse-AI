"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, ArrowRight, Loader2, Sparkles } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";

import { AiInsightPanel } from "@/components/complaints/ai-insight-panel";
import { FormAlert } from "@/components/shared/form-alert";
import { FormField, fieldAria } from "@/components/shared/form-field";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  planSuggestions,
  SUGGESTIBLE_FIELDS,
  suggestedValues,
  type SuggestibleField,
} from "@/features/complaints/ai-suggestions";
import { CATEGORIES, CATEGORY_META, SEVERITIES, SEVERITY_META } from "@/features/complaints/constants";
import { useAnalyzePhoto, useLatestAnalysis, useUpdateComplaint } from "@/features/complaints/hooks";
import { detailsSchema, toDetailsPayload, type DetailsValues } from "@/features/complaints/schemas";
import { isApiError } from "@/lib/api-client";
import type { Complaint } from "@/types/api";

/** ISO timestamp -> "YYYY-MM-DDTHH:mm" in local time, the format <input type="datetime-local"> uses. */
function toDateTimeLocal(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function displayValue(field: SuggestibleField, value: string): string {
  if (field === "category") return CATEGORY_META[value as keyof typeof CATEGORY_META]?.label ?? value;
  if (field === "severity") return SEVERITY_META[value as keyof typeof SEVERITY_META]?.label ?? value;
  return value;
}

interface DetailsStepProps {
  complaint: Complaint;
  onBack: () => void;
  onContinue: () => void;
}

export function DetailsStep({ complaint, onBack, onContinue }: DetailsStepProps) {
  const updateComplaint = useUpdateComplaint(complaint.id);
  const photo = complaint.evidence.find((e) => e.evidence_type === "ORIGINAL");

  const {
    register,
    control,
    handleSubmit,
    setError,
    setValue,
    getValues,
    getFieldState,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: zodResolver(detailsSchema),
    defaultValues: {
      title: complaint.title ?? "",
      // An empty category fails validation with "Choose the type of issue."
      category: (complaint.category ?? "") as DetailsValues["category"],
      severity: complaint.severity ?? "UNKNOWN",
      description: complaint.description ?? "",
      observedAt: toDateTimeLocal(complaint.observed_at),
    },
  });

  // ── AI analysis ───────────────────────────────────────────────────────────
  const latest = useLatestAnalysis(complaint.id);
  const analyze = useAnalyzePhoto(complaint.id);
  const candidate = analyze.data ?? latest.data ?? null;
  // Only an analysis of the *current* photo counts (the photo may have been replaced).
  const analysis = candidate && candidate.evidence_id === photo?.id ? candidate : null;

  // Analyse automatically, once, if this photo hasn't been analysed yet.
  const autoStarted = useRef(false);
  const { mutate: runAnalysis } = analyze;
  useEffect(() => {
    if (autoStarted.current || latest.isPending || !photo || analysis) return;
    autoStarted.current = true;
    runAnalysis(photo.id);
  }, [latest.isPending, photo, analysis, runAnalysis]);

  // When a (new) analysis arrives, fill only the fields the citizen left empty.
  const [aiFilled, setAiFilled] = useState<Set<SuggestibleField>>(new Set());
  const [alternatives, setAlternatives] = useState<Partial<Record<SuggestibleField, string>>>({});
  const appliedFor = useRef<string | null>(null);
  useEffect(() => {
    if (!analysis?.result || appliedFor.current === analysis.id) return;
    appliedFor.current = analysis.id;
    const touched = Object.fromEntries(
      SUGGESTIBLE_FIELDS.map((field) => [field, getFieldState(field).isDirty]),
    );
    const plan = planSuggestions(getValues(), touched, analysis.result);
    for (const [field, value] of Object.entries(plan.fill)) {
      setValue(field as SuggestibleField, value as never, { shouldValidate: false });
    }
    setAiFilled(new Set(Object.keys(plan.fill) as SuggestibleField[]));
    setAlternatives(plan.alternatives);
  }, [analysis, getFieldState, getValues, setValue]);

  const watched = useWatch({ control, name: SUGGESTIBLE_FIELDS });
  const suggestion = analysis?.result ? suggestedValues(analysis.result) : null;

  function aiHint(field: SuggestibleField, index: number): string | undefined {
    // Show "Suggested by AI" only while the field still holds the AI's text.
    if (!suggestion || !aiFilled.has(field) || watched[index] !== suggestion[field]) return undefined;
    return "Suggested by AI. Please check it.";
  }

  function acceptAlternative(field: SuggestibleField) {
    const value = alternatives[field];
    if (value === undefined) return;
    setValue(field, value as never, { shouldDirty: true, shouldValidate: true });
    setAlternatives((previous) => {
      const next = { ...previous };
      delete next[field];
      return next;
    });
  }

  function alternativeFor(field: SuggestibleField): ReactNode {
    const value = alternatives[field];
    if (value === undefined) return null;
    return (
      <div className="flex flex-col gap-2 rounded-lg border border-dashed border-teal/40 bg-teal-soft/30 px-3 py-2 text-sm sm:flex-row sm:items-center sm:justify-between">
        <span>
          <Sparkles className="mr-1 inline size-3.5 text-teal" aria-hidden />
          <span className="text-muted-foreground">AI suggests:</span> {displayValue(field, value)}
        </span>
        <Button type="button" variant="outline" size="sm" onClick={() => acceptAlternative(field)}>
          Use suggestion
        </Button>
      </div>
    );
  }

  const analysing = analyze.isPending || (latest.isPending && !analysis);
  const analysisFailed = !analysis && !analysing && analyze.isError;

  async function onSubmit(values: DetailsValues) {
    try {
      await updateComplaint.mutateAsync(toDetailsPayload(values));
      onContinue();
    } catch (error) {
      setError("root", {
        message: isApiError(error) ? error.message : "Couldn't save the details. Please try again.",
      });
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="grid grid-cols-1 gap-6">
      <div className="grid gap-1">
        <h2 className="text-xl font-semibold">Describe the issue</h2>
        <p className="text-sm text-muted-foreground">
          The AI suggests details from your photo. You stay in control: check them, change
          anything, or fill everything in yourself.
        </p>
      </div>

      {photo && (
        <AiInsightPanel
          state={
            analysing
              ? { kind: "analysing" }
              : analysisFailed
                ? {
                    kind: "error",
                    message: isApiError(analyze.error)
                      ? analyze.error.message
                      : "AI analysis isn't available right now. You can fill in the details yourself.",
                    onRetry: () => analyze.mutate(photo.id),
                  }
                : analysis
                  ? {
                      kind: "ready",
                      analysis,
                      onRetry: () => analyze.mutate(photo.id),
                      retrying: analyze.isPending,
                    }
                  : { kind: "analysing" }
          }
        />
      )}

      <FormAlert message={errors.root?.message} />

      <FormField id="title" label="Title" error={errors.title?.message} hint={aiHint("title", 0)}>
        <Input
          placeholder="e.g. Deep pothole near the school gate"
          {...fieldAria("title", errors.title?.message, aiHint("title", 0))}
          {...register("title")}
        />
        {alternativeFor("title")}
      </FormField>

      <div className="grid gap-5 sm:grid-cols-2">
        <FormField
          id="category"
          label="Type of issue"
          error={errors.category?.message}
          hint={aiHint("category", 1)}
        >
          <Controller
            control={control}
            name="category"
            render={({ field }) => (
              <Select value={field.value ?? ""} onValueChange={field.onChange}>
                <SelectTrigger
                  className="w-full"
                  onBlur={field.onBlur}
                  {...fieldAria("category", errors.category?.message, aiHint("category", 1))}
                >
                  <SelectValue placeholder="Choose a category" />
                </SelectTrigger>
                <SelectContent>
                  {CATEGORIES.map((value) => {
                    const { label, icon: Icon } = CATEGORY_META[value];
                    return (
                      <SelectItem key={value} value={value}>
                        <Icon className="text-teal" aria-hidden /> {label}
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
            )}
          />
          {alternativeFor("category")}
        </FormField>

        <FormField
          id="severity"
          label="How serious is it?"
          hint={aiHint("severity", 2) ?? "Choose “Not sure” if you can't tell. The department will assess it."}
          error={errors.severity?.message}
        >
          <Controller
            control={control}
            name="severity"
            render={({ field }) => (
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger className="w-full" onBlur={field.onBlur} id="severity">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SEVERITIES.map((value) => (
                    <SelectItem key={value} value={value}>
                      {SEVERITY_META[value].label} · {SEVERITY_META[value].description}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
          {alternativeFor("severity")}
        </FormField>
      </div>

      <FormField
        id="description"
        label="Description"
        error={errors.description?.message}
        hint={aiHint("description", 3)}
      >
        <Textarea
          rows={5}
          placeholder="What is the problem, how big is it, and is it causing any danger?"
          {...fieldAria("description", errors.description?.message, aiHint("description", 3))}
          {...register("description")}
        />
        {alternativeFor("description")}
      </FormField>

      <FormField
        id="observedAt"
        label="When did you see it? (optional)"
        error={errors.observedAt?.message}
        className="max-w-xs"
      >
        <Input
          type="datetime-local"
          {...fieldAria("observedAt", errors.observedAt?.message)}
          {...register("observedAt")}
        />
      </FormField>

      <div className="flex justify-between gap-3">
        <Button type="button" variant="outline" size="lg" onClick={onBack}>
          <ArrowLeft aria-hidden /> Back
        </Button>
        <Button type="submit" size="lg" disabled={isSubmitting}>
          {isSubmitting && <Loader2 className="animate-spin" aria-hidden />}
          Continue <ArrowRight aria-hidden />
        </Button>
      </div>
    </form>
  );
}
