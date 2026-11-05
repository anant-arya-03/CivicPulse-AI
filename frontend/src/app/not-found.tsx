import { MapPinOff } from "lucide-react";
import Link from "next/link";

import { Logo } from "@/components/layout/logo";
import { EmptyState } from "@/components/shared/empty-state";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-8 px-4">
      <Logo />
      <EmptyState
        className="w-full max-w-md"
        icon={MapPinOff}
        title="Page not found"
        description="The page you're looking for doesn't exist or has moved."
        action={
          <Button asChild>
            <Link href="/">Go to homepage</Link>
          </Button>
        }
      />
    </div>
  );
}
