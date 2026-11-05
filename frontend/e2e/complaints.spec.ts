import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

const FIXTURES = path.join(__dirname, "fixtures");
const PHOTO = path.join(FIXTURES, "pothole-sample.jpg");
const NOT_AN_IMAGE = path.join(FIXTURES, "not-an-image.txt");

async function registerNewUser(page: Page) {
  const email = `e2e-${Date.now()}-${Math.floor(Math.random() * 1e6)}@civicpulse.example`;
  await page.goto("/register");
  await page.getByLabel("Full name").fill("Report Tester");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("Secret123");
  await page.getByLabel("Confirm password").fill("Secret123");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

/** The page must never scroll sideways (e.g. a wide photo pushing the layout out on a phone).
 * Compare with the device's real width: mobile browsers widen window.innerWidth to fit
 * overflowing content, so it can't be used to detect overflow. */
async function expectNoHorizontalScroll(page: Page) {
  const screenWidth = page.viewportSize()?.width ?? 0;
  const pageWidth = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(pageWidth, "page is wider than the screen").toBeLessThanOrEqual(screenWidth);
}

async function uploadPhoto(page: Page, file: string) {
  // The real <input type="file"> is visually hidden inside the drop zone. It is disabled until
  // the page is interactive, so wait for that before choosing a file.
  const input = page.locator('input[type="file"]').first();
  await expect(input).toBeEnabled();
  await input.setInputFiles(file);
}

test("report a complaint: photo, AI suggestions, edits, location, letter, then track it", async ({
  page,
}) => {
  await registerNewUser(page);
  await expect(page.getByText("No complaints yet")).toBeVisible();

  // ── Step 1: photo ─────────────────────────────────────────────────────────
  await page.goto("/report");
  await expect(page.getByRole("heading", { name: "Upload a photo of the problem" })).toBeVisible();

  await uploadPhoto(page, NOT_AN_IMAGE);
  await expect(page.getByText("Please choose a JPEG, PNG, or WebP photo.")).toBeVisible();

  await uploadPhoto(page, PHOTO);
  await expect(page.getByRole("button", { name: "Replace photo" })).toBeVisible();
  // Navigations get extra time: the dev server compiles each page on its first visit.
  await expect(page).toHaveURL(/\/report\?draft=[0-9a-f-]+&step=1$/, { timeout: 20_000 }); // draft saved
  await expectNoHorizontalScroll(page);
  await page.getByRole("button", { name: "Continue" }).click();

  // ── Step 2: AI analysis (mock provider: pothole scenario) ────────────────
  await expect(page.getByRole("heading", { name: "Describe the issue" })).toBeVisible();
  await expect(page.getByText("What the AI sees")).toBeVisible();
  await expect(page.getByText("Demo AI").first()).toBeVisible(); // never mistaken for a real AI
  await expect(page.getByText("A roughly oval hole in the asphalt")).toBeVisible();
  // Empty fields were filled with suggestions...
  await expect(page.getByLabel("Title")).toHaveValue("Pothole on the road surface");
  await expect(page.getByRole("combobox", { name: "Type of issue" })).toContainText("Road pothole");
  await expect(page.getByText("Suggested by AI. Please check it.").first()).toBeVisible();

  // ...and the citizen corrects them.
  await page.getByLabel("Title").fill("Deep pothole on Lake Road");
  await page.getByLabel("Description").fill("A large pothole filled with water. Two-wheelers swerve around it.");
  await page.getByRole("button", { name: "Continue" }).click();

  // ── Step 3: location (typed by hand, so the test doesn't depend on a geocoder) ──
  await expect(page.getByRole("heading", { name: "Where is the problem?" })).toBeVisible();

  // Going back to step 2: the AI must not overwrite the corrections.
  await page.getByRole("button", { name: "Back" }).click();
  await expect(page.getByLabel("Title")).toHaveValue("Deep pothole on Lake Road");
  await expect(page.getByLabel("Description")).toHaveValue(
    "A large pothole filled with water. Two-wheelers swerve around it.",
  );
  await expect(page.getByText("AI suggests:").first()).toBeVisible(); // offered, not applied
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page.getByRole("heading", { name: "Where is the problem?" })).toBeVisible();
  await page.getByLabel("Street address or landmark").fill("45 Lake Road");
  await page.getByLabel("Neighbourhood / ward (optional)").fill("Lakeside");
  await page.getByLabel("City or town").fill("Demo City");
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByText("Please confirm this is where the problem is.")).toBeVisible();

  await page.getByLabel("I confirm this is where the problem is.").check();
  await page.getByRole("button", { name: "Continue" }).click();

  // ── Step 4: department, matched from the (fictional) demo directory ───────
  await expect(page.getByRole("heading", { name: "Who should handle this?" })).toBeVisible();
  const roads = page.getByRole("radio", { name: "Choose Demo City Roads and Infrastructure Department" });
  await expect(roads).toBeChecked(); // a certain match is pre-selected, but the citizen confirms
  await expect(page.getByText("Demo directory entry").first()).toBeVisible();
  await expect(page.getByText("roads@demo-city.example")).toBeVisible();
  await page.getByRole("button", { name: "Use this department" }).click();

  // ── Step 5: complaint letter, drafted by the (demo) AI, edited by the citizen ──
  await expect(page.getByRole("heading", { name: "Review your complaint letter" })).toBeVisible();
  const letter = page.getByLabel("Letter");
  await expect(letter).toHaveValue(/Dear Sir or Madam/);
  await expect(letter).toHaveValue(/45 Lake Road, Lakeside, Demo City/); // facts from the database
  await expect(letter).toHaveValue(/1 photo attached/);
  await expect(page.getByText("Drafted by AI. Please read it carefully.")).toBeVisible();
  await expectNoHorizontalScroll(page);

  await page.getByLabel("Subject").fill("Urgent repair needed: deep pothole on Lake Road");
  await letter.fill(`${await letter.inputValue()}\n\nP.S. Children cross here every morning.`);
  await page.getByRole("button", { name: "Save and continue" }).click();

  // ── Step 6: preview, explicit approval, simulated send ───────────────────
  await expect(page.getByRole("heading", { name: "Check and send your complaint" })).toBeVisible();
  await expect(page.getByText("Simulation mode.")).toBeVisible();
  const previewBox = page.getByRole("region", { name: "Message preview" });
  await expect(previewBox.getByText("roads@demo-city.example")).toBeVisible();
  await expect(previewBox.getByText("Urgent repair needed: deep pothole on Lake Road")).toBeVisible();
  await expect(previewBox.getByText(/Children cross here every morning/)).toBeVisible();
  await expectNoHorizontalScroll(page);

  const send = page.getByRole("button", { name: /Approve and send \(simulated\)/ });
  await expect(send).toBeDisabled(); // nothing is sent without explicit approval
  await page.getByLabel(/I have reviewed this complaint and approve sending it/).check();
  await send.click();

  // ── Details page ──────────────────────────────────────────────────────────
  await expect(page).toHaveURL(/\/complaints\/[0-9a-f-]+\?submitted=1$/, { timeout: 20_000 });
  await expect(page.getByRole("heading", { level: 1, name: "Deep pothole on Lake Road" })).toBeVisible();
  await expect(page.getByText("Simulated submission complete")).toBeVisible();
  await expect(page.getByText("No email was sent to a real department.").first()).toBeVisible();
  await expect(page.getByText("Submitted", { exact: true }).first()).toBeVisible();
  const history = page.getByRole("heading", { name: "Messages" }).locator("xpath=ancestor::*[@data-slot='card']");
  await expect(history.getByText("Simulated: not delivered to a real department")).toBeVisible();
  await expect(history.getByText("To roads@demo-city.example")).toBeVisible();
  await expect(page.getByText("Road pothole").first()).toBeVisible();
  await expect(page.getByText("45 Lake Road").first()).toBeVisible();
  await expect(page.getByText("Urgent repair needed: deep pothole on Lake Road").first()).toBeVisible();
  await expect(page.getByText(/Children cross here every morning/).first()).toBeVisible();
  await expect(page.getByText("What the AI sees")).toBeVisible();

  const photo = page.getByRole("img", { name: /Photo 1 of Deep pothole/ });
  await expect(photo).toBeVisible();
  // The private evidence endpoint actually served the image to the owner.
  await expect.poll(() => photo.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBe(800);
  await expectNoHorizontalScroll(page);

  const timeline = page.getByRole("list").filter({ hasText: "Complaint draft created." });
  await expect(timeline.getByText("Photo uploaded.")).toBeVisible();
  await expect(timeline.getByText("AI analysed the photo and suggested: Road pothole.")).toBeVisible();
  await expect(timeline.getByText("Location confirmed: Lakeside, Demo City.")).toBeVisible();
  await expect(timeline.getByText("AI drafted the complaint letter.")).toBeVisible();
  await expect(timeline.getByText("Updated complaint letter.")).toBeVisible();
  await expect(timeline.getByText(/Department selected: Demo City Roads/)).toBeVisible();
  await expect(timeline.getByText(/You approved the complaint for sending/)).toBeVisible();
  await expect(timeline.getByText(/Simulated submission to Demo City Roads/)).toBeVisible();

  // A submitted complaint can't be edited any more.
  await expect(page.getByRole("link", { name: "Continue editing" })).toHaveCount(0);

  // ── It shows up in the list (with search) and on the dashboard ──────────
  await page.goto("/complaints");
  await expect(page.getByText("1 complaint", { exact: true })).toBeVisible();
  await page.getByLabel("Search complaints").fill("no-such-thing");
  await page.getByRole("button", { name: "Search" }).click();
  await expect(page.getByText("No complaints match your filters")).toBeVisible();
  await page.getByRole("button", { name: "Clear filters" }).first().click();
  await expect(page.getByRole("link", { name: /Deep pothole on Lake Road/ })).toBeVisible();

  await page.goto("/dashboard");
  const totalCard = page.locator("section[aria-label='Summary'] > *").first();
  await expect(totalCard).toContainText("Total Complaints");
  await expect(totalCard).toContainText("1");
  const pendingCard = page.locator("section[aria-label='Summary'] > *").nth(2);
  await expect(pendingCard).toContainText("Pending Responses");
  await expect(pendingCard).toContainText("1"); // submitted, waiting for the department
  await expect(page.getByRole("heading", { name: "Recent complaints" })).toBeVisible();
  // Recent activity shows the newest events first.
  await expect(page.getByText(/Simulated submission to Demo City Roads/).first()).toBeVisible();
});

test("cancel a draft complaint", async ({ page }) => {
  await registerNewUser(page);
  await page.goto("/report");
  await uploadPhoto(page, PHOTO);
  await expect(page.getByRole("button", { name: "Replace photo" })).toBeVisible();
  await expect(page).toHaveURL(/draft=[0-9a-f-]+/); // wait for the URL to include the draft id

  const draftId = new URL(page.url()).searchParams.get("draft");
  await page.goto(`/complaints/${draftId}`);
  await page.getByRole("button", { name: "Cancel complaint" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Cancel complaint" }).click();

  await expect(page.getByText("Complaint cancelled.").first()).toBeVisible();
  await expect(page.getByText("Cancelled", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Continue editing" })).toHaveCount(0);
});

test("address search with the mock geocoder fills the form", async ({ page }) => {
  await registerNewUser(page);
  const probe = await page.request.get("/api/v1/locations/search?q=lake road");
  const { provider } = (await probe.json()) as { provider: string };
  test.skip(provider !== "mock", "Only runs against the offline mock geocoder.");

  await page.goto("/report");
  await uploadPhoto(page, PHOTO);
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByLabel("Title").fill("Water leaking from pipe");
  await page.getByRole("combobox", { name: "Type of issue" }).click();
  await page.getByRole("option", { name: "Water leakage" }).click();
  await page.getByLabel("Description").fill("Clean water has been leaking onto the road since morning.");
  await page.getByRole("button", { name: "Continue" }).click();

  await page.getByLabel("Search for an address or landmark").fill("lake road");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByText(/sample locations/)).toBeVisible();
  await page.getByRole("button", { name: /45 Lake Road, Lakeside/ }).click();

  await expect(page.getByLabel("Street address or landmark")).toHaveValue("45 Lake Road");
  await expect(page.getByLabel("City or town")).toHaveValue("Demo City");
  await expect(page.getByLabel("Country code")).toHaveValue("XX");
});
