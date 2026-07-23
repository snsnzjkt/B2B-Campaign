import { expect, test } from "@playwright/test";

test("register and see empty leads state", async ({ page }) => {
  const email = `test-${Date.now()}@example.com`;

  await page.goto("/register");
  await page.getByLabel("Organization name").fill("E2E Test Org");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: /register/i }).click();

  await expect(page).toHaveURL(/\/leads/);
  await expect(page.getByText("No leads yet")).toBeVisible();
});

test("unauthenticated visit to /leads redirects to /login", async ({ browser }) => {
  // Fresh, isolated context (no localStorage/cookies from other tests in this file).
  const context = await browser.newContext();
  const page = await context.newPage();

  await page.goto("/leads");
  await expect(page).toHaveURL(/\/login/);

  await context.close();
});
