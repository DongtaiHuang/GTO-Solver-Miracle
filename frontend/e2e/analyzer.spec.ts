import {expect,test} from "@playwright/test";
import {readFile} from "node:fs/promises";

test("import a complete history, step through it, inspect exact decisions and round-trip JSON",async({page,request})=>{
 const index=await (await request.get("/api/strategy/scenarios")).json();
 const s=index.scenarios.find((r:{solution_id:string})=>r.solution_id==="river-550-bb-v1").scenario;
 const history={version:"1.0",hero:"BTN",seats:Object.fromEntries(Object.keys(s.starting_stacks).map(p=>[p,
 {name:p,stack:10000,cards:p==="BTN"?["Ac","Ad"]:p==="BB"?["Kh","Qh"]:null}])),
 big_blind:100,small_blind:50,board:s.board,actions:[...s.history,{position:"BB",street:"river",action:"call",amount:550}]};
 await page.goto("/analyzer");
 await page.getByText("Save, reopen or transfer JSON",{exact:true}).click();
 await page.getByLabel("Import hand JSON").setInputFiles({name:"hand.json",mimeType:"application/json",buffer:Buffer.from(JSON.stringify(history))});
 await expect(page.getByRole("button",{name:"1. preflop · UTG fold",exact:true})).toBeVisible();
 await expect(page.locator(".analyzer-table").getByLabel("Kh",{exact:true})).toHaveCount(0);
 await page.getByRole("button",{name:/river · BTN bet 550/}).click();
 await page.getByLabel("Analyze under these solver ranges and tree").selectOption("river-550-btn-v1");
 await expect(page.getByText(/Recorded action bet@550 costs/)).toBeVisible();
 await page.getByLabel("Opponent model",{exact:true}).selectOption("lp");
 await expect(page.getByLabel("KhQh call@550 (%)")).toHaveValue("90");
 await page.getByLabel("Heads-up equity assumption").selectOption("AA KK QQ AKs");
 await page.getByRole("button",{name:"Calculate hero equity"}).click();
 await expect(page.getByText(/% showdown equity/)).toBeVisible();
 await page.getByRole("button",{name:"Next decision"}).click();
 await expect(page.getByText(/Call pot odds 33.3%/)).toBeVisible();
 await page.getByRole("button",{name:"Next decision"}).click();
 await expect(page.getByText("BTN receives 1650 chips")).toBeVisible();
 await expect(page.locator(".analyzer-table").getByLabel("Kh",{exact:true})).toBeVisible();
 await page.getByRole("button",{name:"Save in this tab"}).click();
 const download=page.waitForEvent("download");await page.getByRole("button",{name:"Export JSON"}).click();
 expect(JSON.parse(await readFile((await (await download).path())!,"utf8"))).toEqual(history);
 await page.reload();await page.getByText("Save, reopen or transfer JSON",{exact:true}).click();
 await page.getByRole("button",{name:"Reopen My hand"}).click();
 await expect(page.getByRole("button",{name:/river · BB call 550/})).toBeVisible();
 await page.getByLabel("Import hand JSON").setInputFiles({name:"bad.json",mimeType:"application/json",buffer:Buffer.from('{"version":"2.0"}')});
 await expect(page.getByRole("main").getByRole("alert").filter({hasText: /Input should be '1\.0'/})).toBeVisible();
 await expect(page.getByRole("button",{name:/river · BB call 550/})).toBeVisible();
});

test("manual action entry follows the engine and hidden cards remain hidden",async({page})=>{
 await page.setViewportSize({width:390,height:844});
 await page.goto("/analyzer");await page.getByText("Enter or edit hand",{exact:true}).click();
 await page.getByLabel("BTN cards",{exact:true}).fill("As Kd");
 await page.getByRole("button",{name:"Validate hand"}).click();
 await page.getByRole("button",{name:"Record fold",exact:true}).click();
 await expect(page.getByRole("heading",{name:"preflop · 150 chips in pot"})).toBeVisible();
 await expect(page.locator(".analyzer-table .acting")).toContainText("HJ");
 await page.getByRole("button",{name:"Previous decision"}).click();
 await expect(page.locator(".analyzer-table .acting")).toContainText("UTG");
 await expect(page.getByText("Solver strategy unavailable for this scenario")).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});

test("review completed trainer hand opens the actual session history",async({page})=>{
 await page.goto("/trainer");await page.getByRole("button",{name:"New Hand"}).click();
 await page.getByRole("button",{name:"Fold",exact:true}).click();
 await page.getByRole("link",{name:"Review This Hand"}).click();
 await expect(page.getByRole("heading",{name:"Hand review workspace"})).toBeVisible();
 await expect(page.getByRole("button",{name:"Next decision"})).toBeEnabled();
 await expect(page.locator(".analyzer-table").getByLabel("Hidden card")).toHaveCount(10);
});
