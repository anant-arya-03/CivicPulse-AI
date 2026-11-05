"use client";

import { ArrowLeft, ArrowRight, Info, ListPlus, Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { AuthorityCard } from "@/components/complaints/authority-card";
import { ErrorState } from "@/components/shared/error-state";
import { FormAlert } from "@/components/shared/form-alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuthorityMatches, useAuthoritySearch, useSelectAuthority } from "@/features/complaints/hooks";
import { initialAuthoritySelection } from "@/features/complaints/submission";
import { isApiError } from "@/lib/api-client";
import type { Authority, Complaint } from "@/types/api";

interface DepartmentStepProps {
  complaint: Complaint;
  onBack: () => void;
  onContinue: () => void;
}

const INTRO = {
  EXACT: "We found the department responsible for this in the directory. Please confirm it.",
  PARTIAL: "More than one department could handle this. Please choose the right one.",
  NONE: "No department in the directory handles this type of issue in this area yet.",
};

/** Step 4: choose the department. Matching is rule-based; the citizen always confirms. */
export function DepartmentStep({ complaint, onBack, onContinue }: DepartmentStepProps) {
  const matches = useAuthorityMatches(complaint.id);
  const selectAuthority = useSelectAuthority(complaint.id);
  const [choice, setChoice] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const others = useAuthoritySearch({ category: complaint.category ?? undefined }, showAll);

  // Pre-select once, when the matches arrive (only if the match is certain).
  const initialised = useRef(false);
  useEffect(() => {
    if (initialised.current || !matches.data) return;
    initialised.current = true;
    setChoice(initialAuthoritySelection(matches.data));
  }, [matches.data]);

  async function confirm() {
    if (!choice) return;
    if (choice !== complaint.authority?.id) {
      try {
        await selectAuthority.mutateAsync(choice);
      } catch {
        return; // shown from selectAuthority.error
      }
    }
    onContinue();
  }

  if (matches.isPending) {
    return (
      <div className="grid gap-3" aria-busy="true" aria-label="Finding the right department">
        <Skeleton className="h-7 w-72" />
        <Skeleton className="h-32 rounded-xl" />
      </div>
    );
  }
  if (matches.isError) {
    return (
      <ErrorState
        message={isApiError(matches.error) ? matches.error.message : "Couldn't load the departments."}
        onRetry={() => matches.refetch()}
      />
    );
  }

  const { confidence } = matches.data;
  const matched = matches.data.matches;
  const shownIds = new Set(matched.map((m) => m.authority.id));
  const extra = (others.data ?? []).filter((a) => !shownIds.has(a.id) && a.official_email);

  return (
    <div className="grid grid-cols-1 gap-6">
      <div className="grid gap-1">
        <h2 className="text-xl font-semibold">Who should handle this?</h2>
        <p className="text-sm text-muted-foreground">{INTRO[confidence]}</p>
      </div>

      {confidence === "NONE" && (
        <p className="flex items-start gap-2 rounded-lg bg-muted px-3 py-2 text-sm text-muted-foreground">
          <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
          You can still finish your complaint letter and send it to the department yourself. We
          never guess contact details: departments are only added from verified official sources.
        </p>
      )}

      {matched.length > 0 && (
        <AuthorityChoices
          label="Matching departments"
          options={matched.map((m) => ({ authority: m.authority, reasons: m.reasons }))}
          choice={choice}
          onChoose={setChoice}
        />
      )}

      {matched.length > 0 && !showAll && (
        <Button type="button" variant="ghost" className="w-fit" onClick={() => setShowAll(true)}>
          <ListPlus aria-hidden /> Show other departments for this issue
        </Button>
      )}
      {showAll && others.isFetching && <Skeleton className="h-24 rounded-xl" />}
      {showAll && !others.isFetching && extra.length === 0 && (
        <p className="text-sm text-muted-foreground">No other departments handle this issue.</p>
      )}
      {extra.length > 0 && (
        <AuthorityChoices
          label="Other departments"
          options={extra.map((authority) => ({ authority }))}
          choice={choice}
          onChoose={setChoice}
        />
      )}

      <FormAlert
        message={
          selectAuthority.isError
            ? isApiError(selectAuthority.error)
              ? selectAuthority.error.message
              : "Couldn't save your choice. Please try again."
            : undefined
        }
      />

      <div className="flex flex-wrap justify-between gap-3">
        <Button type="button" variant="outline" size="lg" onClick={onBack}>
          <ArrowLeft aria-hidden /> Back
        </Button>
        {confidence === "NONE" && !choice ? (
          <Button type="button" size="lg" variant="outline" onClick={onContinue}>
            Continue without a department <ArrowRight aria-hidden />
          </Button>
        ) : (
          <Button type="button" size="lg" disabled={!choice || selectAuthority.isPending} onClick={() => void confirm()}>
            {selectAuthority.isPending && <Loader2 className="animate-spin" aria-hidden />}
            Use this department <ArrowRight aria-hidden />
          </Button>
        )}
      </div>
    </div>
  );
}

function AuthorityChoices({
  label,
  options,
  choice,
  onChoose,
}: {
  label: string;
  options: { authority: Authority; reasons?: string[] }[];
  choice: string | null;
  onChoose: (id: string) => void;
}) {
  return (
    <fieldset className="grid gap-3">
      <legend className="mb-2 text-sm font-medium">{label}</legend>
      {options.map(({ authority, reasons }) => (
        <label key={authority.id} className="block cursor-pointer">
          <AuthorityCard
            authority={authority}
            reasons={reasons}
            selected={choice === authority.id}
            action={
              <input
                type="radio"
                name="authority"
                value={authority.id}
                checked={choice === authority.id}
                onChange={() => onChoose(authority.id)}
                className="mt-1 size-5 accent-[var(--teal)]"
                aria-label={`Choose ${authority.name}`}
              />
            }
          />
        </label>
      ))}
    </fieldset>
  );
}
