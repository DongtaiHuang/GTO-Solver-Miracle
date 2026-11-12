import {expect,test} from "@playwright/test";
test("full-tree comparison edits sparse policies, shows sensitivity and reached matrix",async({page})=>{
 await page.goto("/");
 await page.getByLabel("Supported exact scenario").selectOption("ts-root-v1");
 await page.getByRole("button",{name:"Query exact strategy"}).click();
 const panel=page.getByRole("group",{name:"Multi-street response"});
 await panel.getByText("Inspect equilibrium rows and edit individual assumptions").click();
 await panel.getByLabel("Opponent public history").selectOption("turn/check");
 await panel.getByLabel("Opponent combo",{exact:true}).selectOption("AcAd");
 await panel.getByLabel("bet@275 override (%)",{exact:true}).fill("0");
 await panel.getByRole("button",{name:"Apply combo override"}).click();
 await panel.getByLabel(/Compare opening rates/).check();
 await panel.getByRole("button",{name:"Calculate full-tree response"}).click();
 await expect(panel.getByRole("heading",{name:"Base · root EV (chips)"})).toBeVisible();
 await expect(panel.getByText(/Root gain/)).toHaveCount(3);
 await panel.getByText("Base model · best-response matrix").click();
 await expect(panel.getByRole("group",{name:"Model-conditioned best-response matrix"}).getByRole("button")).toHaveCount(169);
 await panel.getByText(/Policy changes/).first().click();
 await expect(panel.getByText(/turn\/check · AcAd:/).first()).toContainText("bet@275 0.0%");
 await page.getByLabel("Comparison archetype").selectOption("standard_gto");
 await expect(panel.getByLabel("Opening turn bet (%)")).toHaveCount(0);
 await panel.getByRole("button",{name:"Calculate full-tree response"}).click();
 await expect(panel.getByRole("heading",{name:"Equilibrium benchmark · root EV (chips)"})).toBeVisible();
});

test("analyzer exposes a matched turn response and preserves hidden cards",async({page,request})=>{
 const index=await (await request.get("/api/strategy/scenarios")).json();
 const s=index.scenarios.find((r:{solution_id:string})=>r.solution_id==="ts-root-v1").scenario;
 const hand={version:"1.0",hero:"BB",seats:Object.fromEntries(Object.keys(s.starting_stacks).map(p=>[p,
 {name:p,stack:10000,cards:p==="BB"?["Kh","Qh"]:null}])),big_blind:100,small_blind:50,board:s.board,actions:s.history};
 await page.goto("/analyzer");
 await page.getByText("Save, reopen or transfer JSON",{exact:true}).click();
 await page.getByLabel("Import hand JSON").setInputFiles({name:"turn.json",mimeType:"application/json",buffer:Buffer.from(JSON.stringify(hand))});
 await page.getByRole("button",{name:"turn",exact:true}).click();
 await page.getByLabel("Analyze under these solver ranges and tree").selectOption("ts-root-v1");
 await page.getByRole("button",{name:"Calculate full-tree response"}).click();
 await expect(page.getByText(/Root gain/)).toBeVisible();
 await expect(page.locator(".analyzer-table").getByLabel("Hidden card")).toHaveCount(10);
});
