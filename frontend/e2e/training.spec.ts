import { expect, test } from "@playwright/test";
test("mobile practice records and reopens verified attempts", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/training");
  await page.getByLabel("Benchmark").selectOption("tag");
  await page
    .getByLabel("Exercise", { exact: true })
    .selectOption({ label: "ts-root-v1 · BB · KhQh" });
  await page
    .getByRole("button", { name: "bet@275", exact: true })
    .press("Enter");
  await expect(page.getByText(/120.574177 chips/)).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Inspect in Study" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Retry exercise" }).click();
  await page.getByRole("button", { name: "check", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Best or numerically equivalent" }),
  ).toBeVisible();
  await page.reload();
  await page
    .getByText("Performance by session, street, position and scenario")
    .click();
  await expect(page.getByText(/Model · retry · 1\/1 graded/)).toBeVisible();
  const saved = await page.evaluate(() =>
    sessionStorage.getItem("miracle.training.v1"),
  );
  expect(JSON.parse(saved!).attempts).toHaveLength(2);
  await page
    .getByLabel("Replace from JSON")
    .setInputFiles({
      name: "invalid.json",
      mimeType: "application/json",
      buffer: Buffer.from(saved!.replace("120.574176", "123.574176")),
    });
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "failed verification",
  );
  await page
    .getByLabel("Replace from JSON")
    .setInputFiles({
      name: "history.json",
      mimeType: "application/json",
      buffer: Buffer.from(saved!),
    });
  await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});
