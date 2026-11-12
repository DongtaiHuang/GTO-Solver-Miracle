import { test, expect } from "@playwright/test";

test("exact strategy lookup keeps synthetic data opt-in and displays combo-specific mixed strategies", async ({ page }) => {
  await page.goto("/");
  const matrix = page.getByRole("group", { name: "GTO strategy matrix", exact: true });
  await expect(matrix.getByRole("button")).toHaveCount(169);
  await expect(page.getByText(/9 public approved scenarios/)).toBeVisible();
  const demo = page.getByRole("checkbox", { name: /Show synthetic examples/ });
  await expect(demo).not.toBeChecked();
  await expect(page.getByRole("button", { name: "AA strategy unavailable", exact: true })).toBeVisible();
  await demo.check();
  await page.getByLabel("Supported exact scenario").selectOption("synthetic-ui-preflop-v1");
  await page.getByRole("button", { name: "Query exact strategy" }).click();
  const status = page.getByRole("status", { name: "Strategy coverage status" });
  await expect(status).toContainText("SYNTHETIC");
  await expect(page.getByRole("button", { name: "AA strategy coverage 2/6", exact: true })).toBeVisible();
  const details = page.getByRole("region", { name: "Selected hand strategy" });
  await expect(details.getByText("13.3%", { exact: true })).toBeVisible();
  await page.getByLabel("Inspect combination").selectOption("AcAd");
  await expect(details.getByText("10.0%", { exact: true })).toBeVisible();
  await expect(details).toContainText("Validated action EV unavailable");
  await expect(page.getByRole("region", { name: "Solution provenance" })).toContainText("synthetic_only");
  await page.getByText("Edit opponent assumptions", { exact: true }).click();
  await page.getByLabel("Opponent profile", { exact: true }).selectOption("lp");
  await expect(page.getByLabel("VPIP (%)", { exact: true })).toHaveValue("45");
  await expect(page.getByRole("region", { name: "GTO versus opponent comparison" })).toContainText("No exploitative best response");
  await page.screenshot({ path: "test-results/strategy-desktop.png", fullPage: true });

  for (const street of ["flop", "turn", "river"]) {
    await page.getByLabel("Supported exact scenario").selectOption("synthetic-ui-" + street + "-v1");
    await page.getByRole("button", { name: "Query exact strategy" }).click();
    await expect(status).toContainText("SYNTHETIC");
    await expect(page.locator(".strategy-node-summary")).toContainText(street);
    await expect(page.locator(".strategy-node-summary .card")).toHaveCount(
      street === "flop" ? 3 : street === "turn" ? 4 : 5);
  }

  await page.getByText("Complete scenario configuration (JSON)", { exact: true }).click();
  const editor = page.getByLabel("Exact scenario JSON");
  const scenario = JSON.parse(await editor.inputValue());
  scenario.board[0] = "3c";
  await editor.fill(JSON.stringify(scenario));
  await page.getByRole("button", { name: "Query exact strategy" }).click();
  await expect(status).toContainText("GTO solution unavailable");
  await expect(page.getByRole("button", { name: "AA strategy unavailable", exact: true })).toBeVisible();
  await demo.uncheck();
  await expect(page.getByText(/9 public approved scenarios/)).toBeVisible();
  await expect(page.getByText("SYNTHETIC DEMONSTRATION — NOT GTO")).toHaveCount(0);
});

test("strategy dashboard is usable on mobile and retains the range/equity workspace", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.getByText(/9 public approved scenarios/)).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole("checkbox", { name: /Show synthetic examples/ }).check();
  await page.getByLabel("Supported exact scenario").selectOption("synthetic-ui-flop-v1");
  await page.getByRole("button", { name: "Query exact strategy" }).click();
  await expect(page.getByRole("status", { name: "Strategy coverage status" })).toContainText("SYNTHETIC");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole("button", { name: "AKs strategy coverage 2/4", exact: true }).click();
  await expect(page.getByRole("heading", { name: "AKs details" })).toBeVisible();
  await page.screenshot({ path: "test-results/strategy-mobile.png", fullPage: true });
  await page.getByRole("button", { name: "Range editing & equity", exact: true }).click();
  await expect(page.getByText("Model ready", { exact: true })).toBeVisible();
  await expect(page.getByRole("group", { name: "169 starting hand classes" }).getByRole("button")).toHaveCount(169);
});

test("reviewed river strategy shows mixed bluffs, EV and measured accuracy", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Supported exact scenario").selectOption("river-550-btn-v1");
  await page.getByRole("button", { name: "Query exact strategy" }).click();
  await page.getByRole("button", { name: "54s strategy coverage 1/4" }).click();
  const detail = page.getByRole("region", { name: "Selected hand strategy" });
  await expect(detail).toContainText("50.0%");
  await expect(detail.getByRole("row").filter({hasText:"bet to 550"})).toContainText("0.000");
  await expect(page.getByLabel("Solution provenance")).toContainText("Best-response gap");
});

test("river response updates when modeled call rates change", async ({page}) => {
  await page.goto("/");
  await page.getByLabel("Supported exact scenario").selectOption("river-550-btn-v1");
  await page.getByRole("button",{name:"Query exact strategy"}).click();
  const panel=page.getByRole("region",{name:"Model-conditioned river response"});
  await panel.getByText("Edit river probabilities",{exact:true}).click();
  await panel.getByLabel("KhQh call@550 (%)").fill("0");
  await panel.getByLabel("KsJs call@550 (%)").fill("0");
  await expect(panel).toContainText("Gain against model 275.00 chips");
});

test("expanded solver exposes exact raise targets and measured accuracy", async ({page})=>{
  await page.goto("/");
  await page.getByLabel("Supported exact scenario").selectOption("cfr-river-root-v1");
  await page.getByRole("button",{name:"Query exact strategy"}).click();
  const colors = page.locator(".strategy-action-legend span").filter({hasText:/bet to/}).locator("i");
  await expect(colors).toHaveCount(2);
  expect(await colors.evaluateAll(items=>new Set(items.map(item=>getComputedStyle(item).backgroundColor)).size)).toBe(2);
  await page.getByLabel("Supported exact scenario").selectOption("cfr-river-bet275-v1");
  await page.getByRole("button",{name:"Query exact strategy"}).click();
  await expect(page.getByLabel("Solution provenance")).toContainText("CFR+");
  await expect(page.getByLabel("Solution provenance")).toContainText("BR gap");
  await page.getByRole("button",{name:/KQs strategy coverage/}).click();
  await expect(page.getByLabel("Selected hand strategy").getByRole("rowheader",{name:"raise to 1650"})).toBeVisible();
  await expect(page.getByLabel("Model-conditioned river response")).toHaveCount(0);
});


test("desktop study workspace fits the matrix and EVs and supports arrow-key selection",async({page})=>{
  await page.setViewportSize({width:1440,height:900});
  await page.goto("/");
  await page.getByLabel("Supported exact scenario").selectOption("river-550-btn-v1");
  await page.getByRole("button",{name:"Query exact strategy"}).click();
  const matrix=page.getByRole("group",{name:"GTO strategy matrix"});
  const table=page.getByRole("table",{name:"Selected hand action frequencies and EV"});
  await expect(table).toBeVisible();
  for(const item of [matrix,table,page.getByRole("link",{name:/Compare opponent strategies/})]){
    const box=await item.boundingBox();
    expect(box!.y+box!.height).toBeLessThan(900);
  }
  const aa=matrix.getByRole("button",{name:/^AA strategy coverage/});
  await aa.focus(); await page.keyboard.press("ArrowRight");
  await expect(matrix.getByRole("button",{name:"AKs strategy unavailable"})).toBeFocused();
  await expect(page.getByRole("region",{name:"Selected hand strategy"})).toContainText("No strategy data");
  await page.keyboard.press("Home"); await expect(aa).toBeFocused();
  await page.getByRole("link",{name:/Compare opponent strategies/}).click();
  await page.getByLabel("Comparison archetype").selectOption("lp");
  await expect(page.getByLabel("KhQh call@550 (%)")).toHaveValue("90");
});
