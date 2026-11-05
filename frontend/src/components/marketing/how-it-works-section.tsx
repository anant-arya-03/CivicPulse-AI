import { Camera, ClipboardCheck, ScanSearch, TrendingUp } from "lucide-react";

const STEPS = [
  {
    icon: Camera,
    title: "Capture the problem",
    description: "Take or upload a photo of the pothole, broken streetlight, or overflowing bin.",
  },
  {
    icon: ScanSearch,
    title: "AI analyzes the issue",
    description:
      "AI suggests a category, title, and description. You can edit anything it gets wrong.",
  },
  {
    icon: ClipboardCheck,
    title: "Review and submit",
    description:
      "Confirm the location and department, review the formal complaint, then approve sending it.",
  },
  {
    icon: TrendingUp,
    title: "Track and verify",
    description:
      "Follow replies and follow-ups on a clear timeline, and confirm when the fix is real.",
  },
];

export function HowItWorksSection() {
  return (
    <section id="how-it-works" className="scroll-mt-20 border-y border-border bg-card">
      <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:py-24">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-semibold tracking-wide text-teal-strong uppercase">
            How it works
          </p>
          <h2 className="mt-2 text-3xl font-bold sm:text-4xl">From photo to resolution</h2>
          <p className="mt-4 text-muted-foreground">
            Four simple steps, with you in control at every point.
          </p>
        </div>

        <ol className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map(({ icon: Icon, title, description }, index) => (
            <li key={title} className="relative rounded-xl border border-border bg-background p-6">
              <span className="text-xs font-semibold text-muted-foreground">Step {index + 1}</span>
              <span className="mt-3 flex size-11 items-center justify-center rounded-xl bg-navy text-white">
                <Icon className="size-5" aria-hidden />
              </span>
              <h3 className="mt-4 text-lg font-semibold">{title}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{description}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
