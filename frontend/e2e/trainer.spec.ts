import { test, expect } from "@playwright/test";
test("plays a real full-stack hand and resets to the next hand", async ({ page }) => {
  await page.setViewportSize({width:1366,height:768});
  await page.goto("/trainer");
  const newHand = page.getByRole("button", { name: "New Hand" });
  await expect(newHand).toBeEnabled();
  await expect(page.locator(".opponent-setup")).not.toHaveAttribute("open","");
  await newHand.click();
  await expect(page.getByLabel("Your actions")).toBeVisible();
  await expect(page.getByLabel("Hidden card")).toHaveCount(10);
  await expect(newHand).toBeDisabled();
  await expect(page.locator(".seat-profile")).toHaveCount(5);
  const bounds=await page.locator(".action-buttons").boundingBox();
  expect(bounds!.y+bounds!.height).toBeLessThanOrEqual(768);
  await page.screenshot({ path: "test-results/table-desktop.png", fullPage: true });
  for (let turn = 0; turn < 100; turn++) {
    if (await page.getByLabel("Hand result").count()) break;
    const check = page.getByRole("button", { name: "Check", exact: true });
    const call = page.getByRole("button", { name: /^Call / });
    if (await check.count()) await check.click();
    else await call.click();
    await expect(page.getByText("Processing…")).toHaveCount(0);
  }
  await expect(page.getByLabel("Hand result")).toBeVisible();
  await expect(page.getByLabel("Hand result")).toContainText("Hero final stack");
  await expect(newHand).toBeEnabled();
  await newHand.click();
  await expect(page.getByText("#2", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Hidden card")).toHaveCount(10);
});
test("mobile layout fits the viewport and a fold finishes the hand", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/trainer");
  await expect(page.getByRole("button", { name: "New Hand" })).toBeEnabled();
  await page.getByRole("button", { name: "New Hand" }).click();
  await expect(page.getByRole("button", { name: "Fold", exact: true })).toBeEnabled();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(await page.locator(".action-buttons button").evaluateAll(buttons =>
    buttons.every(button => button.scrollWidth <= button.clientWidth))).toBe(true);
  await page.screenshot({ path: "test-results/table-mobile.png", fullPage: true });
  await page.getByRole("button", { name: "Fold", exact: true }).click();
  await expect(page.getByLabel("Hand result")).toBeVisible();
});
