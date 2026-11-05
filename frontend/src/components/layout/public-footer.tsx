import Link from "next/link";

import { Logo } from "@/components/layout/logo";

const FOOTER_COLUMNS = [
  {
    title: "Product",
    links: [
      { href: "/#how-it-works", label: "How It Works" },
      { href: "/#features", label: "Features" },
      { href: "/register", label: "Get Started" },
    ],
  },
  {
    title: "Account",
    links: [
      { href: "/login", label: "Login" },
      { href: "/register", label: "Create account" },
    ],
  },
];

export function PublicFooter() {
  return (
    <footer className="border-t border-border bg-card">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-12 sm:px-6 md:grid-cols-[1.4fr_1fr_1fr_1.4fr]">
        <div className="grid content-start gap-3">
          <Logo />
          <p className="max-w-xs text-sm text-muted-foreground">
            See it. Report it. Track it. Resolve it. A student project exploring AI-assisted
            civic reporting.
          </p>
        </div>

        {FOOTER_COLUMNS.map((column) => (
          <div key={column.title} className="grid content-start gap-3">
            <h2 className="text-sm font-semibold">{column.title}</h2>
            <ul className="grid gap-2">
              {column.links.map((link) => (
                <li key={link.label}>
                  <Link
                    href={link.href}
                    className="text-sm text-muted-foreground hover:text-navy hover:underline"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}

        <div className="grid content-start gap-3" id="privacy">
          <h2 className="text-sm font-semibold">Privacy</h2>
          <p className="text-sm text-muted-foreground">
            Your photos are private to your account, and location metadata is removed from them.
            Nothing is sent to any authority without your explicit approval.
          </p>
          <p className="text-sm text-muted-foreground">
            Contact: <span className="font-medium text-foreground">[project contact email]</span>
          </p>
        </div>
      </div>
      <div className="border-t border-border">
        <p className="mx-auto max-w-6xl px-4 py-5 text-xs text-muted-foreground sm:px-6">
          © CivicPulse AI · Semester project. Not affiliated with any government body.
        </p>
      </div>
    </footer>
  );
}
