import {test,expect} from "@playwright/test";
import {readFile} from "node:fs/promises";

test("completed trainer hands are captured once and visible in Study in the same tab",async({page})=>{
  await page.goto("/trainer");
  await page.getByRole("button",{name:"New Hand"}).click();
  await page.getByRole("button",{name:"Fold",exact:true}).click();
  await expect(page.getByRole("link",{name:"Review This Hand"})).toBeVisible();
  await page.reload();
  await page.getByText("Opponent observations",{exact:true}).click();
  const player=page.getByLabel("Observed player");
  await player.selectOption("bot-2");
  await expect(page.getByRole("heading",{name:"Morgan · 1 observed hands"})).toBeVisible();
  await page.getByRole("link",{name:/Study Ranges/}).click();
  await page.getByText("Opponent observations",{exact:true}).click();
  await page.getByLabel("Observed player").selectOption("bot-2");
  await expect(page.getByText(/Heuristic Trainer actions/)).toBeVisible();
});

test("manual mapping, duplicate rejection, override, export, delete and restore",async({page})=>{
  await page.goto("/analyzer");
  await page.getByRole("button",{name:"Record fold",exact:true}).click();
  await page.getByText("Opponent observations",{exact:true}).click();
  await page.getByText("Add this hand to opponent observations",{exact:true}).click();
  await page.getByLabel("Hand reference").fill("review-001");
  await page.getByLabel("Map UTG",{exact:true}).selectOption("new");
  await page.getByRole("button",{name:"Record mapped players"}).click();
  await expect(page.getByRole("heading",{name:"UTG · 1 observed hands"})).toBeVisible();
  await expect(page.getByRole("row").filter({has:page.getByRole("rowheader",{name:"VPIP",exact:true})})).toContainText("0/1");
  await page.getByRole("button",{name:"Record mapped players"}).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Duplicate");
  await page.getByLabel("Manual label override",{exact:true}).selectOption("tag");
  await expect(page.getByText("Label updated.",{exact:true})).toBeVisible();
  await page.getByText("Manage observation archive",{exact:true}).click();
  const download=page.waitForEvent("download");await page.getByRole("button",{name:"Export observations"}).click();
  const raw=await readFile((await (await download).path())!);
  const archive=JSON.parse(raw.toString());
  expect(archive.entries).toHaveLength(1);expect(Object.values(archive.overrides)).toEqual(["tag"]);
  page.on("dialog",d=>d.accept());
  await page.getByRole("button",{name:"Delete player observations"}).click();
  await expect(page.getByText("No observed players in this tab.")).toBeVisible();
  await page.getByLabel("Import observations",{exact:true}).setInputFiles({name:"observed.json",mimeType:"application/json",buffer:raw});
  await expect(page.getByRole("heading",{name:"UTG · 1 observed hands"})).toBeVisible();
  await expect(page.getByLabel("Manual label override",{exact:true})).toHaveValue("tag");
  await page.getByRole("button",{name:"Reset observations"}).click();
  await expect(page.getByText("No observed players in this tab.")).toBeVisible();
});

test("adopt a provisional Trainer preset explicitly for the next hand",async({page})=>{
  // Synthetic records confined to this isolated test context.
  const seats=Object.fromEntries(["UTG","HJ","CO","BTN","SB","BB"].map(p=>[p,{name:p,stack:10000,cards:null}]));
  const actions=["UTG","HJ","CO","BTN","SB","BB"].map((position,i)=>({position,street:"preflop",action:i?"fold":"raise",amount:i?null:250}));
  const entries=Array.from({length:20},(_,i)=>({hand_id:"test-"+i,source:"trainer",mapping:{UTG:"bot-3"},
    hand:{trainer_hand_id:"test-"+i,version:"1.0",seats,hero:"BTN",small_blind:50,big_blind:100,board:[],actions}}));
  await page.goto("/trainer");
  await page.evaluate(records=>sessionStorage.setItem("miracle.observations.v1",JSON.stringify({version:"1.0",entries:records,overrides:{}})),entries);
  await page.getByText("Opponent observations",{exact:true}).click();
  await page.getByRole("button",{name:"Use inferred LAG preset next hand"}).click();
  const sent=page.waitForRequest(r=>r.method()==="POST"&&r.url().endsWith("/api/games"));
  await page.getByRole("button",{name:"New Hand"}).click();
  expect((await sent).postDataJSON().opponents[2].id).toBe("lag");
  await expect(page.getByRole("button",{name:"Fold",exact:true})).toBeEnabled();
  await expect(page.getByRole("button",{name:"Use inferred LAG preset next hand"})).toHaveCount(0);
});
