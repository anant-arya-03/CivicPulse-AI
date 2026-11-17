import fs from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";
import { FIXTURES, registerNewUser } from "./helpers";

test("a Noida report can explicitly choose a demo department and simulate submission", async ({ page }, testInfo) => {
  await registerNewUser(page);
  const csrf = (await page.context().cookies()).find(cookie => cookie.name === "cp_csrf")!.value;
  const headers = { "X-CSRF-Token": csrf };
  const created = await page.request.post("/api/v1/complaints", { headers, data: {
    title: "Road damage in Noida", description: "A pothole near the crossing needs repair.", category: "ROAD_POTHOLE",
  } });
  expect(created.ok()).toBeTruthy();
  const { id } = await created.json();
  const photo = await page.request.post(`/api/v1/complaints/${id}/evidence`, { headers, multipart: {
    file: { name: "pothole.jpg", mimeType: "image/jpeg", buffer: fs.readFileSync(path.join(FIXTURES, "pothole-sample.jpg")) },
  } });
  expect(photo.ok()).toBeTruthy();
  const location = await page.request.patch(`/api/v1/complaints/${id}`, { headers, data: {
    address_line: "Sector 18 crossing", city: "Noida", country: "IN", confirm_location: true,
  } });
  expect(location.ok()).toBeTruthy();
  await page.goto(`/report?draft=${id}&step=4`);
  await page.getByRole("button", { name: "Show demo departments" }).click();
  const option = page.getByRole("radio", { name: "Choose Demo City Roads and Infrastructure Department" });
  await expect(option).toBeVisible();
  await expect(option).not.toBeChecked();
  await expect(page.getByText(/Your entered location stays unchanged/)).toBeVisible();
  await page.addScriptTag({ path: path.resolve("node_modules/axe-core/axe.min.js") });
  const violations = await page.evaluate(async () => {
    const axe = (window as unknown as { axe: { run: () => Promise<{ violations: { id: string; nodes: { html: string; failureSummary: string }[] }[] }> } }).axe;
    return (await axe.run()).violations.map(({ id, nodes }) => ({ id, nodes: nodes.map(({ html, failureSummary }) => ({ html, failureSummary })) }));
  });
  expect(violations).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(page.viewportSize()!.width);
  await page.screenshot({ path: testInfo.outputPath("department-demo.png"), fullPage: true });
  await option.check();
  await page.getByRole("button", { name: "Use demo department" }).click();
  await expect(page).toHaveURL(new RegExp(`draft=${id}&step=5`));
  await page.getByRole("button", { name: "Save and continue" }).click();
  await page.getByLabel(/I have reviewed this complaint and approve/).check();
  await page.getByRole("button", { name: "Approve and send (simulated)", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/complaints/${id}`));
  const saved = await (await page.request.get(`/api/v1/complaints/${id}`)).json();
  expect(saved.city).toBe("Noida");
  expect(saved.country).toBe("IN");
  expect(saved.authority.is_demo).toBe(true);
  expect(saved.status).toBe("SUBMITTED");
  const history = await (await page.request.get(`/api/v1/complaints/${id}/communications`)).json();
  expect(history[0].delivery_status).toBe("SIMULATED_SENT");
});
