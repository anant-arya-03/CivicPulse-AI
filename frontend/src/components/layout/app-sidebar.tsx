"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense } from "react";

import { Logo } from "@/components/layout/logo";
import { APP_NAV_ITEMS, isActivePath } from "@/components/layout/nav-config";
import { UserMenu } from "@/components/layout/user-menu";
import { cn } from "@/lib/utils";
import type { User } from "@/types/api";

/** Desktop navigation (shown at the `lg` breakpoint and wider). `user` is undefined while loading. */
export function AppSidebar({ user }: { user?: User }) {
  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col bg-sidebar lg:flex">
      <div className="flex h-16 items-center px-5">
        <Logo href="/dashboard" tone="light" />
      </div>

      {/* The current path is only known at request time on dynamic routes, so the
          highlighted version streams in; the fallback is the same links without a highlight. */}
      <Suspense fallback={<SidebarLinks pathname={null} />}>
        <CurrentSidebarLinks />
      </Suspense>

      <div className="mt-auto border-t border-sidebar-border p-3">
        {user ? (
          <UserMenu user={user} variant="sidebar" />
        ) : (
          <div className="flex items-center gap-3 p-2" aria-hidden>
            <span className="size-9 animate-pulse rounded-full bg-sidebar-accent" />
            <span className="grid flex-1 gap-1.5">
              <span className="h-3 w-24 animate-pulse rounded bg-sidebar-accent" />
              <span className="h-2.5 w-32 animate-pulse rounded bg-sidebar-accent" />
            </span>
          </div>
        )}
      </div>
    </aside>
  );
}

function CurrentSidebarLinks() {
  return <SidebarLinks pathname={usePathname()} />;
}

function SidebarLinks({ pathname }: { pathname: string | null }) {
  return (
    <nav aria-label="App" className="grid gap-1 px-3 py-4">
      {APP_NAV_ITEMS.map(({ href, label, icon: Icon }) => {
        const active = pathname !== null && isActivePath(pathname, href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "relative flex h-11 items-center gap-3 rounded-lg px-3 text-sm font-medium transition-colors",
              active
                ? "bg-sidebar-accent text-white"
                : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-white",
            )}
          >
            {active && <span className="absolute inset-y-2 left-0 w-1 rounded-r bg-teal" aria-hidden />}
            <Icon className={cn("size-5", active && "text-teal")} aria-hidden />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
