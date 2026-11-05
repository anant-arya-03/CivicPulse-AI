import { expect, test } from "@playwright/test";

import { registerNewUser, submitComplaintViaApi } from "./helpers";

test("no reply: a reminder is suggested, approved and sent; then replies update the case", async ({ page }) => {
  await registerNewUser(page);
  const id = await submitComplaintViaApi(page);
  await page.goto(`/complaints/${id}`);

  // ── Waiting for the department ──────────────────────────────────────────
  const tracking = page.getByRole("heading", { name: "Response tracking" }).locator("xpath=ancestor::*[@data-slot='card']");
  await expect(tracking.getByText(/If there's no reply by/)).toBeVisible();
  await expect(tracking.getByText(/listed for this department \(7 days\)/)).toBeVisible();
  await expect(tracking.getByText("0 of 2 reminders sent")).toBeVisible();
  const demo = page.getByRole("heading", { name: "Demo tools" }).locator("xpath=ancestor::*[@data-slot='card']");
  await expect(demo.getByText("Nothing real is sent or received.")).toBeVisible();

  // ── The deadline passes: a reminder is drafted, NOT sent ────────────────
  await demo.getByRole("button", { name: "Skip ahead to the next check" }).click();
  const reminder = page.getByRole("region", { name: "Reminder 1" });
  await expect(reminder.getByText("Nothing is sent unless you approve it.", { exact: false })).toBeVisible();
  await expect(reminder.getByText("roads@demo-city.example", { exact: true })).toBeVisible();
  const sendButton = reminder.getByRole("button", { name: "Approve and send reminder (simulated)" });
  await expect(sendButton).toBeDisabled();

  await page.goto("/dashboard");
  const attention = page.getByRole("region", { name: "Needs your attention" });
  await expect(attention.getByText("Reminder to review")).toBeVisible();
  await attention.getByRole("link", { name: /Deep pothole on Lake Road/ }).click();

  // ── The citizen approves and sends it (simulated) ───────────────────────
  await page.getByRole("region", { name: "Reminder 1" }).getByLabel(/I have reviewed this reminder/).check();
  await page.getByRole("button", { name: "Approve and send reminder (simulated)" }).click();
  await expect(tracking.getByText("1 of 2 reminders sent")).toBeVisible();
  await expect(page.getByRole("region", { name: "Reminder 1" })).toHaveCount(0);
  const messages = page.getByRole("heading", { name: "Messages" }).locator("xpath=ancestor::*[@data-slot='card']");
  await expect(messages.getByText("Reminder 1 to roads@demo-city.example")).toBeVisible();
  await expect(messages.getByText("Simulated: not delivered to a real department")).toHaveCount(2);

  // ── The department acknowledges (simulated) ─────────────────────────────
  await demo.getByLabel("Simulated reply from the department").selectOption("acknowledged");
  await demo.getByRole("button", { name: "Simulate reply" }).click();
  await expect(page.getByText("Acknowledged", { exact: true }).first()).toBeVisible();
  await expect(tracking.getByText(/^DC-RD-\d+$/)).toBeVisible();
  await expect(messages.getByText("Simulated reply: not from a real department")).toBeVisible();

  // ── It says it's fixed: reminders stop, only the citizen can confirm ─────
  await demo.getByLabel("Simulated reply from the department").selectOption("resolved");
  await demo.getByRole("button", { name: "Simulate reply" }).click();
  await expect(page.getByText("Awaiting your verification").first()).toBeVisible();
  await expect(tracking.getByText(/Only you can confirm/)).toBeVisible();
  await expect(tracking.getByText(/If there's no reply by/)).toHaveCount(0);

  const timeline = page.getByRole("list").filter({ hasText: "Complaint draft created." });
  await expect(timeline.getByText(/Reminder 1 is ready for you to review/)).toBeVisible();
  await expect(timeline.getByText(/Simulated: Reminder 1 sent to Demo City Roads/)).toBeVisible();
  await expect(timeline.getByText(/Department reference number recorded/)).toBeVisible();
  await expect(timeline.getByText(/Reminders stopped because the department says/)).toBeVisible();

  const pageWidth = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(pageWidth, "page is wider than the screen").toBeLessThanOrEqual(page.viewportSize()?.width ?? 0);
});
