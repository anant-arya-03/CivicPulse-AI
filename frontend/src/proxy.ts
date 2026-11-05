import { NextResponse, type NextRequest } from "next/server";

const SESSION_COOKIE_NAME = "cp_session";

/**
 * Optimistic route protection: if there is no session cookie at all, send the visitor to
 * /login before the page even loads.
 *
 * This is only a UX shortcut. It cannot tell a valid session from an expired one; the
 * backend checks that on every API call, and AppShell redirects if /auth/me returns 401.
 */
export function proxy(request: NextRequest) {
  if (request.cookies.has(SESSION_COOKIE_NAME)) return NextResponse.next();

  const loginUrl = new URL("/login", request.url);
  loginUrl.searchParams.set("next", request.nextUrl.pathname);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  // Only the authenticated app pages. API calls (/api/v1/...) are never touched here.
  matcher: ["/dashboard/:path*", "/report/:path*", "/complaints/:path*", "/settings/:path*"],
};
