"use client";

import { Plus } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense } from "react";

import { Logo } from "@/components/layout/logo";
import { APP_NAV_ITEMS, isActivePath } from "@/components/layout/nav-config";
import { UserMenu } from "@/components/layout/user-menu";
import { cn } from "@/lib/utils";
import type { User } from "@/types/api";

/** Mobile/tablet top bar (below the `lg` breakpoint). `user` is undefined while loading. */
export function AppMobileTopBar({ user }: { user?: User }) {
  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-card/95 px-4 backdrop-blur lg:hidden">
      <Logo href="/dashboard" />
      {user ? (
        <UserMenu user={user} />
      ) : (
        <span className="m-1 size-9 animate-pulse rounded-full bg-muted" aria-hidden />
      )}
    </header>
  );
}

// Settings is reachable from the avatar menu in the top bar, keeping three tabs with Report centred.
const MOBILE_TAB_HREFS = ["/dashboard", "/report", "/complaints"];
const MOBILE_TABS = MOBILE_TAB_HREFS.map((href) => APP_NAV_ITEMS.find((item) => item.href === href)!);

/** Mobile bottom tab bar with a prominent centre "Report" button. */
export function AppMobileTabBar() {
  return (
    <nav
      aria-label="App"
      className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-card pb-[env(safe-area-inset-bottom)] lg:hidden"
    >
      {/* Same pattern as the sidebar: the highlighted tab streams in on dynamic routes. */}
      <Suspense fallback={<TabLinks pathname={null} />}>
        <CurrentTabLinks />
      </Suspense>
    </nav>
  );
}

function CurrentTabLinks() {
  return <TabLinks pathname={usePathname()} />;
}

function TabLinks({ pathname }: { pathname: string | null }) {
  return (
    <ul className="mx-auto grid h-16 max-w-md grid-cols-3 items-center">
      {MOBILE_TABS.map(({ href, label, icon: Icon }) => {
        const active = pathname !== null && isActivePath(pathname, href);
        if (href === "/report") {
          return (
            <li key={href} className="flex justify-center">
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className="-mt-6 flex flex-col items-center gap-1 text-xs font-medium text-navy"
              >
                <span className="flex size-12 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-raised ring-4 ring-background">
                  <Plus className="size-6" aria-hidden />
                </span>
                Report
              </Link>
            </li>
          );
        }
        return (
          <li key={href}>
            <Link
              href={href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex h-16 flex-col items-center justify-center gap-1 text-xs font-medium",
                active ? "text-teal-strong" : "text-muted-foreground",
              )}
            >
              <Icon className="size-5" aria-hidden />
              {label.replace("My ", "")}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
