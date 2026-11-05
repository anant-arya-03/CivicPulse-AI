import { ArrowRight, ShieldCheck } from "lucide-react";
import Link from "next/link";

import { HeroPreview } from "@/components/marketing/hero-preview";
import { Button } from "@/components/ui/button";

export function HeroSection() {
  return (
    <section className="mx-auto grid max-w-6xl items-center gap-12 px-4 pt-12 pb-16 sm:px-6 md:pt-20 lg:grid-cols-2 lg:gap-16 lg:pb-24">
      <div className="grid gap-6">
        <span className="inline-flex w-fit items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-sm font-medium text-teal-strong">
          <span className="size-2 rounded-full bg-teal" aria-hidden />
          See it. Report it. Track it. Resolve it.
        </span>

        <h1 className="text-4xl leading-[1.15] font-bold sm:text-5xl">
          Your City. Your Voice. <span className="text-teal-strong">Smarter Civic Action.</span>
        </h1>

        <p className="max-w-xl text-lg text-muted-foreground">
          Report public infrastructure problems in seconds. Let AI help prepare your complaint,
          find the responsible department, and track progress toward resolution.
        </p>

        <div className="flex flex-col gap-3 sm:flex-row">
          <Button asChild size="lg">
            <Link href="/report">
              Report an Issue <ArrowRight aria-hidden />
            </Link>
          </Button>
          <Button asChild size="lg" variant="outline">
            <Link href="#how-it-works">Explore How It Works</Link>
          </Button>
        </div>

        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <ShieldCheck className="size-4 text-success" aria-hidden />
          Nothing is sent to any department without your approval.
        </p>
      </div>

      <HeroPreview />
    </section>
  );
}
