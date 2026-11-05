"use client";

import { FileWarning } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import type { ReactNode } from "react";

import { PageHeader } from "@/components/layout/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useComplaint } from "@/features/complaints/hooks";
import { DepartmentStep } from "@/features/complaints/report-wizard/department-step";
import { DetailsStep } from "@/features/complaints/report-wizard/details-step";
import { LetterStep } from "@/features/complaints/report-wizard/letter-step";
import { LocationStep } from "@/features/complaints/report-wizard/location-step";
import { PhotoStep } from "@/features/complaints/report-wizard/photo-step";
import { StepIndicator, type WizardStep } from "@/features/complaints/report-wizard/step-indicator";
import { SubmitStep } from "@/features/complaints/report-wizard/submit-step";
import { furthestAllowedStep } from "@/features/complaints/submission";
import { isApiError } from "@/lib/api-client";

const STEPS: WizardStep[] = [
  { number: 1, label: "Photo" },
  { number: 2, label: "Details" },
  { number: 3, label: "Location" },
  { number: 4, label: "Department" },
  { number: 5, label: "Letter" },
  { number: 6, label: "Submit" },
];

/**
 * The multi-step report form.
 *
 * The draft is saved on the server after every step, and the URL remembers where you are
 * (`/report?draft=<id>&step=2`), so refreshing or coming back later continues the same draft.
 */
export function ReportWizard() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const draftId = searchParams.get("draft");
  const requestedStep = Number(searchParams.get("step") ?? "1");

  const { data: complaint, isPending, error } = useComplaint(draftId);

  function goTo(step: number, id: string | null = draftId) {
    router.replace(id ? `/report?draft=${id}&step=${step}` : "/report", { scroll: true });
  }

  if (draftId && isPending) return <WizardSkeleton />;

  if (draftId && error) {
    return (
      <WizardFrame current={1}>
        <EmptyState
          icon={FileWarning}
          title={isApiError(error, 404) ? "Draft not found" : "We couldn't load this draft"}
          description="It may have been removed. You can start a new report instead."
          action={
            <Button asChild>
              <Link href="/report">Start a new report</Link>
            </Button>
          }
        />
      </WizardFrame>
    );
  }

  if (complaint && !complaint.available_actions.includes("edit")) {
    return (
      <WizardFrame current={STEPS.length}>
        <EmptyState
          icon={FileWarning}
          title="This complaint can't be edited anymore"
          description="It has been submitted or cancelled. You can still view its details."
          action={
            <Button asChild>
              <Link href={`/complaints/${complaint.id}`}>View complaint</Link>
            </Button>
          }
        />
      </WizardFrame>
    );
  }

  // Never further than the draft allows (see furthestAllowedStep for the rules).
  const step = Math.min(Math.max(requestedStep || 1, 1), furthestAllowedStep(complaint));

  return (
    <WizardFrame current={step}>
      {step === 1 && (
        <PhotoStep
          complaint={complaint}
          onDraftCreated={(id) => goTo(1, id)}
          onContinue={() => goTo(2)}
        />
      )}
      {step === 2 && complaint && (
        <DetailsStep complaint={complaint} onBack={() => goTo(1)} onContinue={() => goTo(3)} />
      )}
      {step === 3 && complaint && (
        <LocationStep complaint={complaint} onBack={() => goTo(2)} onSaved={() => goTo(4)} />
      )}
      {step === 4 && complaint && (
        <DepartmentStep complaint={complaint} onBack={() => goTo(3)} onContinue={() => goTo(5)} />
      )}
      {step === 5 && complaint && (
        <LetterStep
          complaint={complaint}
          onBack={() => goTo(4)}
          onSaved={() =>
            complaint.authority
              ? goTo(6)
              : router.push(`/complaints/${complaint.id}?saved=1`) // no department: save only
          }
        />
      )}
      {step === 6 && complaint && (
        <SubmitStep
          complaint={complaint}
          onGoTo={(n) => goTo(n)}
          onSubmitted={() => router.push(`/complaints/${complaint.id}?submitted=1`)}
        />
      )}
    </WizardFrame>
  );
}

function WizardFrame({ current, children }: { current: number; children: ReactNode }) {
  return (
    <div className="grid grid-cols-1 gap-6">
      <PageHeader
        title="Report an issue"
        description="Your draft is saved after every step, so you can come back to it any time."
      />
      <StepIndicator steps={STEPS} current={current} />
      <Card>
        <CardContent>{children}</CardContent>
      </Card>
    </div>
  );
}

export function WizardSkeleton() {
  return (
    <div className="grid gap-6" aria-busy="true" aria-label="Loading the report form">
      <Skeleton className="h-9 w-56" />
      <Skeleton className="h-11 w-full rounded-lg" />
      <Skeleton className="h-96 w-full rounded-xl" />
    </div>
  );
}
