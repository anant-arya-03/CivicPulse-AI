"use client";

import { Check } from "lucide-react";
import { useEffect, useRef } from "react";

import { cn } from "@/lib/utils";

export interface WizardStep {
  number: number;
  label: string;
  /** Steps that aren't built yet are shown so users see the whole journey. */
  comingSoon?: boolean;
}

export function StepIndicator({ steps, current }: { steps: WizardStep[]; current: number }) {
  // On narrow screens the strip scrolls sideways; keep the current step visible.
  const activeRef = useRef<HTMLLIElement>(null);
  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: "nearest", inline: "center" });
  }, [current]);

  return (
    <nav aria-label="Report progress">
      <ol
        tabIndex={0}
        aria-label="Steps"
        className="flex gap-1.5 overflow-x-auto rounded-lg pb-1 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none sm:gap-2"
      >
        {steps.map((step) => {
          // A "soon" step is never shown as completed: it simply hasn't been built yet.
          const done = step.number < current && !step.comingSoon;
          const active = step.number === current;
          return (
            <li
              key={step.number}
              ref={active ? activeRef : undefined}
              aria-current={active ? "step" : undefined}
              className={cn(
                // relative: keeps the screen-reader-only text inside the scrolling strip (no page overflow)
                "relative flex min-w-fit flex-1 items-center gap-2 rounded-lg border px-2.5 py-2 text-sm",
                active && "border-teal bg-teal-soft font-semibold text-teal-strong",
                done && "border-border bg-card text-foreground",
                !active && !done && "border-dashed border-input text-muted-foreground",
              )}
            >
              <span
                className={cn(
                  "flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                  done && "bg-success text-white",
                  active && "bg-teal text-white",
                  !active && !done && "bg-muted",
                )}
              >
                {done ? <Check className="size-3.5" strokeWidth={3} aria-hidden /> : step.number}
              </span>
              <span className="whitespace-nowrap">
                {step.label}
                {step.comingSoon && <span className="ml-1 text-xs font-normal">(soon)</span>}
                {done && <span className="sr-only"> (completed)</span>}
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
