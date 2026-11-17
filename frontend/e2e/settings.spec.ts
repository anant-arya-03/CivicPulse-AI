import path from "node:path";
import { expect, test } from "@playwright/test";
import { registerNewUser } from "./helpers";
test("preferences persist and notification bell is keyboard reachable", async ({ page }, testInfo) => {
  await registerNewUser(page);
  await page.goto("/settings");
  await page.getByLabel("Include map coordinates in new letters").uncheck();
  await page.getByRole("button", { name: "Save preferences" }).click();
  await expect(page.getByText("Preferences saved.")).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Include map coordinates in new letters")).not.toBeChecked();
  const bell = page.locator("summary").filter({ hasText: "Notifications" });
  await bell.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("region", { name: "Notifications", exact: true })).toBeVisible();
  await page.addScriptTag({ path: path.resolve("node_modules/axe-core/axe.min.js") });
  const violations = await page.evaluate(async () => {
    const axe = (window as unknown as { axe: { run: () => Promise<{ violations: { id: string; description: string }[] }> } }).axe;
    return (await axe.run()).violations.map(({ id, description }) => ({ id, description }));
  });
  expect(violations).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath("settings.png"), fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(page.viewportSize()!.width);
});
