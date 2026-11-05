import { Activity } from "lucide-react";
import Link from "next/link";

import { cn } from "@/lib/utils";

interface LogoProps {
  href?: string;
  /** "dark" = navy text for light backgrounds, "light" = white text for the navy sidebar. */
  tone?: "dark" | "light";
  className?: string;
}

export function Logo({ href = "/", tone = "dark", className }: LogoProps) {
  return (
    <Link
      href={href}
      className={cn("inline-flex items-center gap-2 rounded-lg font-semibold", className)}
      aria-label="CivicPulse AI home"
    >
      <span className="flex size-8 items-center justify-center rounded-lg bg-teal text-white">
        <Activity className="size-4.5" strokeWidth={2.5} aria-hidden />
      </span>
      <span className={cn("text-lg tracking-tight", tone === "dark" ? "text-navy" : "text-white")}>
        CivicPulse <span className={tone === "dark" ? "text-teal-strong" : "text-teal-soft"}>AI</span>
      </span>
    </Link>
  );
}
