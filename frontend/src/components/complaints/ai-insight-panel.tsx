import { AlertTriangle, Eye, HelpCircle, Loader2, RefreshCw, Sparkles } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { CATEGORY_META, SEVERITY_META } from "@/features/complaints/constants";
import { cn } from "@/lib/utils";
import type { AnalysisRead } from "@/types/api";

/** "Demo AI" for the mock provider, so a sample result is never mistaken for a real one. */
export function AiSourceBadge({ isMock, className }: { isMock: boolean; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap",
        isMock
          ? "border border-dashed border-warning text-warning-strong"
          : "bg-teal-soft text-teal-strong",
        className,
      )}
      title={isMock ? "Sample answer from the demo AI. It did not look at your photo." : undefined}
    >
      <Sparkles className="size-3" aria-hidden />
      {isMock ? "Demo AI" : "AI"}
    </span>
  );
}

type PanelState =
  | { kind: "analysing" }
  | { kind: "error"; message: string; onRetry: () => void }
  | { kind: "ready"; analysis: AnalysisRead; onRetry?: () => void; retrying?: boolean };

/** What the AI saw in the photo. Always presented as a suggestion for the citizen to check. */
export function AiInsightPanel({ state, className }: { state: PanelState; className?: string }) {
  if (state.kind === "analysing") {
    return (
      <Frame className={className}>
        <p role="status" className="flex items-center gap-2 text-sm font-medium text-teal-strong">
          <Loader2 className="size-4 animate-spin" aria-hidden />
          Looking at your photo… You can keep typing meanwhile.
        </p>
      </Frame>
    );
  }

  if (state.kind === "error") {
    return (
      <Frame className={cn("border-warning/40 bg-warning-soft", className)}>
        <div role="alert" className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="flex items-start gap-2 text-sm text-warning-strong">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
            {state.message}
          </p>
          <Button type="button" variant="outline" size="sm" onClick={state.onRetry}>
            <RefreshCw aria-hidden /> Try again
          </Button>
        </div>
      </Frame>
    );
  }

  const { analysis } = state;
  const result = analysis.result;
  if (!result) return null;
  const category = CATEGORY_META[result.category];

  return (
    <Frame className={className}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-navy">
          <Sparkles className="size-4 text-teal" aria-hidden />
          What the AI sees
          <AiSourceBadge isMock={analysis.is_mock} />
        </h3>
        {state.onRetry && (
          <Button type="button" variant="ghost" size="sm" onClick={state.onRetry} disabled={state.retrying}>
            {state.retrying ? <Loader2 className="animate-spin" aria-hidden /> : <RefreshCw aria-hidden />}
            Analyse again
          </Button>
        )}
      </div>

      {!result.is_civic_issue && (
        <p className="mt-3 flex items-start gap-2 rounded-lg bg-warning-soft px-3 py-2 text-sm text-warning-strong">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
          The AI couldn&apos;t see a clear civic problem in this photo. You can still continue.
        </p>
      )}

      <dl className="mt-3 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
        <div className="flex gap-1.5">
          <dt className="text-muted-foreground">Likely issue:</dt>
          <dd className="font-medium">
            {category.label}{" "}
            <span className="font-normal text-muted-foreground">
              ({result.category_confidence.toLowerCase()} confidence)
            </span>
          </dd>
        </div>
        <div className="flex gap-1.5">
          <dt className="text-muted-foreground">Severity:</dt>
          <dd className="font-medium">
            {result.severity === "UNKNOWN" ? "Can't tell from the photo" : `Potentially ${SEVERITY_META[result.severity].label.toLowerCase()}`}
          </dd>
        </div>
      </dl>

      <InsightList icon={<Eye className="size-3.5" aria-hidden />} title="Visible in the photo" items={result.observations} />
      <InsightList icon={<HelpCircle className="size-3.5" aria-hidden />} title="Not certain" items={result.uncertainties} />
      <InsightList
        icon={<AlertTriangle className="size-3.5" aria-hidden />}
        title="Please check"
        items={result.warnings}
        tone="warning"
      />

      <p className="mt-3 text-xs text-muted-foreground">
        AI suggestions can be wrong. Please check them and correct anything that isn&apos;t right.
      </p>
    </Frame>
  );
}

function Frame({ children, className }: { children: ReactNode; className?: string }) {
  return <section className={cn("rounded-xl border border-teal/30 bg-teal-soft/40 p-4", className)}>{children}</section>;
}

function InsightList({
  icon,
  title,
  items,
  tone,
}: {
  icon: ReactNode;
  title: string;
  items: string[];
  tone?: "warning";
}) {
  if (items.length === 0) return null;
  return (
    <div className="mt-3">
      <p className={cn("flex items-center gap-1.5 text-xs font-semibold", tone === "warning" ? "text-warning-strong" : "text-navy")}>
        {icon} {title}
      </p>
      <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm text-foreground">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
