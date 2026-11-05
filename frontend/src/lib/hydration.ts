"use client";

import type { UseQueryResult } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";

const noopSubscribe = () => () => {};

/** `false` while React renders on the server and while it hydrates that HTML; `true` afterwards. */
export function useHydrated(): boolean {
  return useSyncExternalStore(
    noopSubscribe,
    () => true, // in the browser, after hydration
    () => false, // on the server, and during hydration
  );
}

/**
 * Why this exists: pages are prerendered as HTML without any user data. While React is still
 * "hydrating" that HTML in the browser, TanStack Query may already have data cached (the current
 * user loads very early). Rendering it straight away would make the browser's first render
 * differ from the HTML, a "hydration mismatch" error.
 *
 * So until hydration finishes, a query reports "still loading", exactly like the server did.
 * After that, cached data shows instantly as usual (e.g. on client-side navigation).
 */
export function useHydrationSafeQuery<TData, TError>(
  result: UseQueryResult<TData, TError>,
): UseQueryResult<TData, TError> {
  const hydrated = useHydrated();
  if (hydrated) return result;
  return {
    ...result,
    data: undefined,
    error: null,
    status: "pending",
    isPending: true,
    isLoading: true,
    isSuccess: false,
    isError: false,
    isLoadingError: false,
    isRefetchError: false,
    isPlaceholderData: false,
  } as UseQueryResult<TData, TError>;
}
