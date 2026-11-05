import { expect, test, type Page } from "@playwright/test";

function uniqueEmail() {
  return `e2e-${Date.now()}-${Math.floor(Math.random() * 1e6)}@civicpulse.example`;
}

async function registerNewUser(page: Page, name = "Test Citizen") {
  const email = uniqueEmail();
  await page.goto("/register");
  await page.getByLabel("Full name").fill(name);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("Secret123");
  await page.getByLabel("Confirm password").fill("Secret123");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  return email;
}

test("landing page shows the hero and key sections", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { level: 1, name: /Your City\. Your Voice\./ }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "From photo to resolution" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "AI Image Analysis" })).toBeVisible();
});

test("protected pages redirect to login when logged out", async ({ page }) => {
  await page.goto("/settings");
  await expect(page).toHaveURL(/\/login\?next=%2Fsettings$/);
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
});

test("register, see dashboard, update profile, log out, log back in", async ({ page }) => {
  const email = await registerNewUser(page);

  await expect(page.getByRole("heading", { name: "Welcome, Test" })).toBeVisible();
  await expect(page.getByText("Total Complaints")).toBeVisible();
  await expect(page.getByText("No complaints yet")).toBeVisible();

  // Update the profile name (exercises a CSRF-protected PATCH through the Next.js proxy).
  await page.goto("/settings");
  await page.getByLabel("Full name").fill("Renamed Citizen");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("Profile updated.")).toBeVisible();

  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "Welcome, Renamed" })).toBeVisible();

  // Log out through the account menu (visible on both desktop sidebar and mobile top bar).
  await page.getByRole("button", { name: "Account menu" }).locator("visible=true").click();
  await page.getByRole("menuitem", { name: "Log out" }).click();
  await expect(page).toHaveURL(/\/login$/);

  // The old session no longer works.
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login/);

  // Wrong password shows an error; the right one logs in and honours ?next=.
  await page.goto("/login?next=/settings");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill("Wrong1234");
  await page.getByRole("button", { name: "Log in" }).click();
  // (Not getByRole("alert"): Next.js's route announcer also uses role="alert".)
  await expect(page.getByText("Incorrect email or password.")).toBeVisible();

  await page.getByLabel("Password", { exact: true }).fill("Secret123");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).toHaveURL(/\/settings$/);
  // The email also appears in the account menu, so look inside the Account details list.
  await expect(page.locator("dd", { hasText: email })).toBeVisible();
});

test("registering with an existing email shows a field error", async ({ page, context }) => {
  const email = await registerNewUser(page);
  await context.clearCookies();

  await page.goto("/register");
  await page.getByLabel("Full name").fill("Someone Else");
  await page.getByLabel("Email").fill(email.toUpperCase());
  await page.getByLabel("Password", { exact: true }).fill("Secret123");
  await page.getByLabel("Confirm password").fill("Secret123");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByText("An account with this email already exists.")).toBeVisible();
});
