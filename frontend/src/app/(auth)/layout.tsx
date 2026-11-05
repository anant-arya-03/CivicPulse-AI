import Link from "next/link";
import type { ReactNode } from "react";

import { Logo } from "@/components/layout/logo";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center px-4 py-10">
      <header className="mb-8">
        <Logo />
      </header>
      <main className="w-full max-w-md">{children}</main>
      <footer className="mt-8">
        <Link href="/" className="text-sm text-muted-foreground hover:text-navy hover:underline">
          ← Back to home
        </Link>
      </footer>
    </div>
  );
}
