/**
 * Validate a `?next=` redirect target so login can't be abused to send users to another site
 * (an "open redirect"). Only same-site paths like "/complaints/123" are allowed.
 */
export function getSafeRedirect(next: string | null | undefined, fallback = "/dashboard"): string {
  if (!next || !next.startsWith("/")) return fallback;
  // "//evil.com" and "/\evil.com" are treated by browsers as other origins.
  if (next.startsWith("//") || next.startsWith("/\\")) return fallback;
  if (next.startsWith("/login") || next.startsWith("/register")) return fallback;
  return next;
}
