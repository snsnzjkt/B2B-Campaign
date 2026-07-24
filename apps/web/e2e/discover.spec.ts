import { expect, test } from "@playwright/test";

test("search, select, and import a discovered lead", async ({ page }) => {
  const email = `discover-${Date.now()}@example.com`;

  await page.goto("/register");
  await page.getByLabel("Organization name").fill("Discover Test Org");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: /register/i }).click();
  await expect(page).toHaveURL(/\/leads/);

  await page.route("**/api/v1/discovery/search", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        candidates: [
          {
            name: "Acme Corp",
            website: "https://acme.com",
            phone: "+1 303-555-0100",
            address: "123 Main St, Denver, CO",
            external_id: "place-1",
            already_imported: false,
          },
        ],
      }),
    });
  });

  await page.route("**/api/v1/discovery/import", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ created: 1, skipped_duplicate: 0 }),
    });
  });

  await page.getByRole("navigation").getByRole("link", { name: "Discover" }).click();
  await expect(page).toHaveURL(/\/leads\/discover/);

  await page.getByLabel("What").fill("marketing agencies");
  await page.getByLabel("Where").fill("Denver, CO");
  await page.getByRole("button", { name: /^search$/i }).click();

  await expect(page.getByText("Acme Corp")).toBeVisible();

  await page.getByRole("checkbox").click();
  await page.getByRole("button", { name: /import selected/i }).click();

  await expect(page.getByText(/imported 1 lead/i)).toBeVisible();
});
