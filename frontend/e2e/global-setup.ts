/**
 * Warm up the dev server before the tests run. `next dev` compiles each page the first time it
 * is requested, which can take longer than a test's 5-second wait on a fresh server (and all
 * tests ask for the same pages at the same moment). Requesting each page once avoids that.
 */
const BASE_URL = "http://localhost:3000";
const PAGES = ["/", "/login", "/register", "/dashboard", "/complaints", "/report", "/settings", "/complaints/warm-up"];

export default async function globalSetup() {
  for (const page of PAGES) {
    try {
      await fetch(BASE_URL + page, { redirect: "manual" });
    } catch {
      // A page that fails here will fail (with a clearer message) in the tests themselves.
    }
  }
}
