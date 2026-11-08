import { test, expect } from "@playwright/test";

test("explicit river range produces exact equity and simplified call EV", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Model ready")).toBeVisible();
  await page.getByLabel("Hero hole cards", { exact: true }).fill("As Ah");
  await page.getByLabel("Street", { exact: true }).selectOption("river");
  await page.getByLabel("Community cards", { exact: true }).fill("2c 3d 7h 8c Jd");
  await page.getByLabel("Pot (chips)", { exact: true }).fill("300");
  await page.getByLabel("Opponent profile", { exact: true }).selectOption("standard_gto");
  await expect(page.getByRole("button", { name: "AA inclusion 0%" })).toBeVisible();
  await page.getByRole("button", { name: "KK inclusion 0%" }).click();
  await expect(page.getByText("Model ready")).toBeVisible();
  await page.getByRole("button", { name: "Calculate equity", exact: true }).click();
  const result = page.getByLabel("Equity results", { exact: true });
  await expect(result).toContainText("Exact enumeration");
  await expect(result.getByText("100.00%", { exact: true })).toHaveCount(2);
  await page.getByLabel("Hero call amount (chips)", { exact: true }).fill("100");
  await page.getByRole("button", { name: "Calculate pot odds", exact: true }).click();
  await expect(page.getByLabel("Pot odds results")).toContainText("25.00%");
  await expect(page.getByLabel("Pot odds results")).toContainText("300.00 chips");
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: "test-results/equity-desktop.png", fullPage: true });

  // Shared royal flush: the same real evaluator must return a split, never a winner.
  await page.getByLabel("Hero hole cards", { exact: true }).fill("2c 3d");
  await page.getByLabel("Community cards", { exact: true }).fill("Ts Js Qs Ks As");
  await expect(result).toHaveCount(0);
  await page.getByRole("button", { name: "Calculate equity", exact: true }).click();
  await expect(result).toContainText("50.00%");
  await expect(result).toContainText("100.00%");
});

test("preflop Monte Carlo is seeded and a changed input requires manual recalculation", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Model ready")).toBeVisible();
  await page.getByLabel("Hero hole cards", { exact: true }).fill("As Ah");
  await page.getByLabel("Opponent equity input").selectOption("hand");
  await page.getByLabel("Opponent hole cards", { exact: true }).fill("Ks Kh");
  await page.getByLabel("Calculation method", { exact: true }).selectOption("monte_carlo");
  await page.getByLabel("Simulations", { exact: true }).fill("500");
  await page.getByLabel("Random seed", { exact: true }).fill("7");
  const response = () => page.waitForResponse(r => r.url().endsWith("/api/equity/hand-vs-hand") && r.request().method() === "POST");
  const firstResponse = response();
  await page.getByRole("button", { name: "Calculate equity", exact: true }).click();
  const first = await (await firstResponse).json();
  await expect(page.getByLabel("Equity results")).toContainText("500 valid samples · seed 7");
  await expect(page.getByLabel("Equity results")).toContainText("95% simultaneous Hoeffding interval");
  const secondResponse = response();
  await page.getByRole("button", { name: "Calculate equity", exact: true }).click();
  const second = await (await secondResponse).json();
  expect(second).toEqual(first);
  await page.getByLabel("Dead cards", { exact: true }).fill("As");
  await expect(page.getByLabel("Equity results")).toHaveCount(0);
  await page.getByRole("button", { name: "Calculate equity", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "distinct valid cards" })).toContainText("distinct valid cards");
});

test("mobile equity requires an explicit profile range assumption", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.getByText("Model ready")).toBeVisible();
  await page.getByLabel("Hero hole cards", { exact: true }).fill("As Ah");
  const button = page.getByRole("button", { name: "Calculate equity", exact: true });
  await expect(button).toBeDisabled();
  await expect(page.getByText("No calibrated range for this profile, position, and history.")).toBeVisible();
  await expect(page.getByText("Model ready")).toBeVisible();
  await page.getByRole("button", { name: "Use displayed range as assumption" }).click();
  await expect(button).toBeEnabled();
  await page.getByLabel("Simulations", { exact: true }).fill("500");
  await button.click();
  await expect(page.getByLabel("Equity results")).toContainText("Monte Carlo estimate");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: "test-results/equity-mobile.png", fullPage: true });
});
