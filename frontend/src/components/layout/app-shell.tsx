"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { AppMobileTabBar, AppMobileTopBar } from "@/components/layout/app-mobile-nav";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { ErrorState } from "@/components/shared/error-state";
import { useCurrentUser } from "@/features/authentication/hooks";
import { isApiError } from "@/lib/api-client";

/**
 * Layout for every authenticated page.
 *
 * The navigation and the page render immediately, so Next.js can prerender them into the
 * static shell for instant navigation. Parts that need the user show skeletons until
 * `/auth/me` answers. A 401 (missing or expired session) redirects to /login.
 *
 * The real security check happens on the backend: every API call needs a valid session,
 * so rendering a page frame before the user is known never exposes private data.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { data: user, error, refetch } = useCurrentUser();
  const isUnauthenticated = isApiError(error, 401);

  useEffect(() => {
    if (isUnauthenticated) {
      // Read the URL only at redirect time. (usePathname() here would block prerendering of
      // dynamic routes like /complaints/[id], whose path is only known at request time.)
      const here = window.location.pathname + window.location.search;
      router.replace(`/login?next=${encodeURIComponent(here)}`);
    }
  }, [isUnauthenticated, router]);

  const loadFailed = error && !isUnauthenticated;

  return (
    <div className="min-h-dvh">
      <AppSidebar user={user} />
      <AppMobileTopBar user={user} />
      <main className="pb-24 lg:pb-0 lg:pl-64">
        <div className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:px-8 lg:py-10">
          {loadFailed ? (
            <ErrorState
              message={isApiError(error) ? error.message : "Something went wrong loading your account."}
              onRetry={() => refetch()}
            />
          ) : (
            children
          )}
        </div>
      </main>
      <AppMobileTabBar />
    </div>
  );
}
