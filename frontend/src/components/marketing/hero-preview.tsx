import { Building2, Check, Construction, MapPin, Sparkles } from "lucide-react";

const TIMELINE = [
  { label: "Photo uploaded", done: true },
  { label: "AI analysis complete", done: true },
  { label: "Department identified", done: true },
  { label: "Awaiting your approval", done: false },
];

/** A static, illustrative preview of the reporting workflow. Clearly labelled as an example. */
export function HeroPreview() {
  return (
    <div className="relative mx-auto w-full max-w-md lg:max-w-none" aria-hidden>
      <div className="absolute -inset-4 -z-10 rounded-[2rem] bg-teal-soft/70 blur-2xl" />

      <div className="rounded-2xl border border-border bg-card p-5 shadow-raised sm:p-6">
        <div className="flex items-center justify-between">
          <span className="rounded-full border border-dashed border-input px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
            Example preview
          </span>
          <span className="text-xs text-muted-foreground">Draft · Step 4 of 6</span>
        </div>

        <div className="mt-4 flex gap-4">
          <div className="flex size-24 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-slate-200 to-slate-300 text-slate-500">
            <Construction className="size-9" />
          </div>
          <div className="grid min-w-0 content-start gap-2">
            <p className="font-semibold text-navy">Damaged road with pothole</p>
            <div className="flex flex-wrap gap-1.5">
              <span className="rounded-full bg-teal-soft px-2 py-0.5 text-xs font-medium text-teal-strong">
                Road Pothole
              </span>
              <span className="rounded-full bg-warning-soft px-2 py-0.5 text-xs font-medium text-warning-strong">
                Potentially high severity
              </span>
            </div>
            <p className="flex items-center gap-1 text-xs text-muted-foreground">
              <MapPin className="size-3.5 shrink-0" /> Location confirmed by you
            </p>
          </div>
        </div>

        <div className="mt-4 rounded-xl border border-border bg-background p-3">
          <p className="flex items-center gap-1.5 text-xs font-semibold text-teal-strong">
            <Sparkles className="size-3.5" /> AI observations
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            A visible pothole on the roadway that may pose a risk to road users. Depth cannot be
            judged from the photo.
          </p>
        </div>

        <div className="mt-3 flex items-center gap-3 rounded-xl border border-border p-3">
          <span className="flex size-9 items-center justify-center rounded-lg bg-secondary text-navy">
            <Building2 className="size-4.5" />
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-navy">Public Works Department</p>
            <p className="text-xs text-muted-foreground">Matched from a verified directory</p>
          </div>
        </div>

        <ol className="mt-4 grid gap-2">
          {TIMELINE.map((step) => (
            <li key={step.label} className="flex items-center gap-2.5 text-sm">
              <span
                className={
                  step.done
                    ? "flex size-5 items-center justify-center rounded-full bg-success text-white"
                    : "size-5 rounded-full border-2 border-dashed border-teal"
                }
              >
                {step.done && <Check className="size-3" strokeWidth={3} />}
              </span>
              <span className={step.done ? "text-foreground" : "font-medium text-teal-strong"}>
                {step.label}
              </span>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
