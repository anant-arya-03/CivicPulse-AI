import Link from "next/link";

import { Button } from "@/components/ui/button";

export function CtaSection() {
  return (
    <section className="mx-auto max-w-6xl px-4 pb-16 sm:px-6 lg:pb-24">
      <div className="flex flex-col items-start gap-6 rounded-2xl bg-navy px-6 py-10 sm:px-10 md:flex-row md:items-center md:justify-between">
        <div className="grid gap-2">
          <h2 className="text-2xl font-bold text-white sm:text-3xl">Spotted a problem today?</h2>
          <p className="text-slate-300">Create a free account and report it in a few minutes.</p>
        </div>
        <Button asChild size="lg" className="bg-white text-navy hover:bg-slate-100">
          <Link href="/register">Get Started</Link>
        </Button>
      </div>
    </section>
  );
}
