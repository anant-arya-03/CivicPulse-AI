import { BellRing, Building2, FileText, Image as ImageIcon, MailCheck, ShieldCheck } from "lucide-react";

const FEATURES = [
  {
    icon: ImageIcon,
    title: "AI Image Analysis",
    description:
      "Identifies the likely civic issue from your photo and notes what it can't be sure about.",
  },
  {
    icon: Building2,
    title: "Smart Department Identification",
    description:
      "Matches the issue and location to a responsible authority from a verified directory, never invented contacts.",
  },
  {
    icon: FileText,
    title: "Automated Complaint Drafting",
    description:
      "Turns confirmed facts into a clear, formal complaint that you can edit before anything is sent.",
  },
  {
    icon: MailCheck,
    title: "Response Monitoring",
    description:
      "Recognises acknowledgements, reference numbers, and status updates in replies from departments.",
  },
  {
    icon: BellRing,
    title: "Intelligent Follow-ups",
    description:
      "Suggests polite reminders at sensible intervals and offers verified escalation contacts when needed.",
  },
  {
    icon: ShieldCheck,
    title: "Resolution Verification",
    description:
      "Compares before-and-after photos to help you check a fix, and you have the final say.",
  },
];

export function FeaturesSection() {
  return (
    <section id="features" className="scroll-mt-20">
      <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:py-24">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-semibold tracking-wide text-teal-strong uppercase">Features</p>
          <h2 className="mt-2 text-3xl font-bold sm:text-4xl">An assistant for the whole journey</h2>
          <p className="mt-4 text-muted-foreground">
            Not just a chatbot: a case manager that keeps your complaint moving.
          </p>
        </div>

        <ul className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, description }) => (
            <li
              key={title}
              className="rounded-xl border border-border bg-card p-6 shadow-card transition-shadow hover:shadow-raised"
            >
              <span className="flex size-11 items-center justify-center rounded-xl bg-teal-soft text-teal">
                <Icon className="size-5" aria-hidden />
              </span>
              <h3 className="mt-4 text-lg font-semibold">{title}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{description}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
