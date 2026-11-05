import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { FIXTURES, registerNewUser, simulateReply, submitComplaintViaApi } from "./helpers";

async function uploadAfterPhoto(page: Page, file: string) {
  const card = page.locator("#check-repair");
  // The file input is disabled until the page is interactive (see ImageDropzone).
  const input = card.locator('input[type="file"]').first();
  await expect(input).toBeEnabled();
  await input.setInputFiles(path.join(FIXTURES, file));
  await expect(card.getByText("The AI thinks:")).toBeVisible({ timeout: 20_000 });
}

async function decide(page: Page, answer: RegExp, notes?: string) {
  const card = page.locator("#check-repair");
  await card.getByLabel(answer).check();
  if (notes) await card.getByLabel(/What did you find/).fill(notes);
  await card.getByLabel(/I checked the place myself/).check();
  await card.getByRole("button", { name: "Save my decision" }).click();
}

test("a claimed repair is checked with a photo, disputed, then confirmed by the citizen", async ({ page }) => {
  await registerNewUser(page);
  const id = await submitComplaintViaApi(page);
  await simulateReply(page, id, "resolved");
  await page.goto(`/complaints/${id}`);

  // ── The department says it's fixed: only the citizen can confirm ────────
  await expect(page.getByText("Awaiting your verification").first()).toBeVisible();
  const check = page.locator("#check-repair");
  await expect(check.getByText(/Take a new photo of the same place/)).toBeVisible();
  const statusCard = page.getByRole("complementary", { name: "Status and department" });
  await expect(statusCard.getByRole("link", { name: "Check the repair" })).toBeVisible();

  // ── First check: the AI thinks it's repaired, the citizen disagrees ─────
  await uploadAfterPhoto(page, "repaired-road.jpg");
  const comparison = page.getByRole("region", { name: "Before and after" });
  await expect(comparison.getByRole("img", { name: "Before (your complaint)" })).toBeVisible();
  await expect(comparison.getByText("Appears repaired")).toBeVisible();
  await expect(comparison.getByText("Demo AI")).toBeVisible();
  await expect(comparison.getByText(/Only your own check decides/)).toBeVisible();
  const save = check.getByRole("button", { name: "Save my decision" });
  await expect(save).toBeDisabled();

  await decide(page, /No, it's not fixed/, "The hole was only half filled.");
  await expect(page.getByText("Reopened", { exact: true }).first()).toBeVisible();

  // ── A message for the department is prepared, sent only after approval ──
  const notice = page.getByRole("region", { name: "Message: not fixed" });
  await expect(notice.getByText("The hole was only half filled.", { exact: false })).toBeVisible();
  await notice.getByLabel(/I have reviewed this message/).check();
  await notice.getByRole("button", { name: "Approve and send message (simulated)" }).click();
  await expect(page.getByRole("region", { name: "Message: not fixed" })).toHaveCount(0);
  const messages = page.getByRole("heading", { name: "Messages" }).locator("xpath=ancestor::*[@data-slot='card']");
  await expect(messages.getByText('"Not fixed" message to roads@demo-city.example')).toBeVisible();

  // ── The department claims a repair again; this time it is fixed ─────────
  await simulateReply(page, id, "resolved");
  await page.reload();
  await uploadAfterPhoto(page, "repaired-road-2.jpg");
  await decide(page, /Yes, it's fixed/);
  await expect(page.getByText("Verified resolved").first()).toBeVisible();

  // ── An audited history; the complaint can be reopened if it comes back ──
  const history = page.getByRole("region", { name: "Earlier checks" });
  await expect(history.getByText("You confirmed it's fixed")).toBeVisible();
  await expect(history.getByText("You said it's not fixed")).toBeVisible();
  await expect(history.getByText("“The hole was only half filled.”")).toBeVisible();
  await expect(page.getByRole("button", { name: "Reopen complaint" })).toBeVisible();

  const timeline = page.getByRole("list").filter({ hasText: "Complaint draft created." });
  await expect(timeline.getByText(/found the issue is not fixed. The complaint is reopened/)).toBeVisible();
  await expect(timeline.getByText(/confirmed the issue is fixed/)).toBeVisible();
  await expect(timeline.getByText(/compared the photos: appears repaired/).first()).toBeVisible();

  await page.goto("/dashboard");
  await expect(page.locator("section[aria-label='Summary'] > *").nth(3)).toContainText("1"); // verified

  await page.goto(`/complaints/${id}`);
  await expect(page.getByText("Verified resolved").first()).toBeVisible();
  const width = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(width, "page is wider than the screen").toBeLessThanOrEqual(page.viewportSize()?.width ?? 0);
});
