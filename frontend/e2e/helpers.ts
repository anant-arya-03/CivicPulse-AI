import fs from "node:fs";
import path from "node:path";

import { expect, type Page } from "@playwright/test";

export const FIXTURES = path.join(__dirname, "fixtures");
const PHOTO = path.join(FIXTURES, "pothole-sample.jpg");

/** Shared by the end-to-end specs that start from an already submitted complaint. */

export async function registerNewUser(page: Page) {
  const email = `e2e-${Date.now()}-${Math.floor(Math.random() * 1e6)}@civicpulse.example`;
  await page.goto("/register");
  await page.getByLabel("Full name").fill("Journey Tester");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("Secret123");
  await page.getByLabel("Confirm password").fill("Secret123");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

/** The report wizard is covered by complaints.spec.ts; here the complaint is prepared through
 * the same API the wizard uses, then approved and sent (simulated). */
export async function submitComplaintViaApi(page: Page): Promise<string> {
  const csrf = (await page.context().cookies()).find((c) => c.name === "cp_csrf")?.value ?? "";
  const headers = { "X-CSRF-Token": csrf };
  const api = (p: string) => `/api/v1${p}`;
  async function ok<T = unknown>(response: Awaited<ReturnType<Page["request"]["get"]>>): Promise<T> {
    expect(response.ok(), await response.text()).toBeTruthy();
    return (await response.json()) as T;
  }

  const complaint = await ok<{ id: string }>(
    await page.request.post(api("/complaints"), {
      headers,
      data: { title: "Deep pothole on Lake Road", description: "A deep pothole near the school gate.", category: "ROAD_POTHOLE" },
    }),
  );
  const id: string = complaint.id;
  await ok(
    await page.request.post(api(`/complaints/${id}/evidence`), {
      headers,
      multipart: { file: { name: "pothole.jpg", mimeType: "image/jpeg", buffer: fs.readFileSync(PHOTO) } },
    }),
  );
  await ok(
    await page.request.patch(api(`/complaints/${id}`), {
      headers,
      data: { address_line: "45 Lake Road", city: "Demo City", state: "Demo State", confirm_location: true },
    }),
  );
  const matches = await ok<{ matches: { authority: { id: string } }[] }>(await page.request.get(api(`/complaints/${id}/authority-matches`)));
  await ok(await page.request.put(api(`/complaints/${id}/authority`), { headers, data: { authority_id: matches.matches[0].authority.id } }));
  await ok(await page.request.post(api(`/complaints/${id}/complaint-draft`), { headers, data: { mode: "template" } }));
  const preview = await ok<{ content_sha256: string }>(await page.request.get(api(`/complaints/${id}/submission-preview`)));
  const message = await ok<{ id: string }>(
    await page.request.post(api(`/complaints/${id}/approve`), {
      headers,
      data: { confirm: true, content_sha256: preview.content_sha256 },
    }),
  );
  await ok(await page.request.post(api(`/communications/${message.id}/send`), { headers }));
  return id;
}

/** A simulated department reply (needs ENABLE_SIMULATION on the backend, as in playwright.config). */
export async function simulateReply(page: Page, complaintId: string, scenario: string) {
  const csrf = (await page.context().cookies()).find((c) => c.name === "cp_csrf")?.value ?? "";
  const response = await page.request.post(`/api/v1/complaints/${complaintId}/simulation/reply`, {
    headers: { "X-CSRF-Token": csrf },
    data: { scenario },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
}
