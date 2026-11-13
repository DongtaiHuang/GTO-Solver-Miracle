import { test, expect } from "@playwright/test";
import {emptyHand} from "../lib/analyzer";
test("guest account offers explicit sign-in and retains tab data on service failure", async ({
  page,
}) => {
  await page.route("**/api/account/me", (r) =>
    r.fulfill({ status: 401, json: { detail: "Sign in required" } }),
  );
  await page.route("**/api/account/challenge", (r) =>
    r.fulfill({ status: 503, json: { detail: "Sign-in is not configured" } }),
  );
  await page.goto("/account");
  await expect(
    page.getByRole("heading", { name: "Guest workspace" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Sign in with Google" }).click();
  await expect(page.locator("main [role=alert]")).toContainText(
    "Sign-in is not configured",
  );
});
test("signed-in archive replacement reports a stale revision without clearing evidence", async ({
  page,
}) => {
  const archive = { version: "1.0", entries: [], overrides: {} };
  await page.addInitScript(
    (a) => sessionStorage.setItem("miracle.observations.v1", JSON.stringify(a)),
    archive,
  );
  await page.route("**/api/account/**", (r) => {
    const path = new URL(r.request().url()).pathname.split("/").pop();
    if (path === "observations" && r.request().method() === "POST")
      return r.fulfill({
        status: 409,
        json: { detail: "Archive changed. Reload before replacing." },
      });
    return r.fulfill({
      json:
        path === "me"
          ? { name: "Practice player" }
          : path === "observations"
            ? { revision: 2, archive }
            : [],
    });
  });
  await page.goto("/account");
  await expect(page.getByText(/Last loaded server revision 2/)).toBeVisible();
  page.once("dialog", (d) => d.accept());
  await page
    .getByRole("button", { name: "Replace server observations" })
    .click();
  await expect(page.locator("main [role=alert]")).toContainText(
    "Archive changed",
  );
  expect(
    await page.evaluate(() =>
      sessionStorage.getItem("miracle.observations.v1"),
    ),
  ).toBe(JSON.stringify(archive));
});

test("test provider callback opens a private account, imports practice, exports evidence and signs out", async ({page})=>{
  let signed=false, merged=false;
  const hand=emptyHand();hand.seats.BTN.name="QA reviewer";
  let stored:unknown;
  await page.addInitScript(h=>sessionStorage.setItem("miracle.analyzer.v1.Reviewed hand",JSON.stringify(h)),hand);
  await page.setViewportSize({width:390,height:844});
  await page.addInitScript(()=>sessionStorage.setItem("miracle.training.v1",JSON.stringify({version:"1",attempts:[]})));
  await page.route("https://accounts.google.com/gsi/client",r=>r.fulfill({contentType:"text/javascript",body:
    "let cb; window.google={accounts:{id:{initialize:o=>cb=o.callback,renderButton:el=>{const b=document.createElement('button');b.textContent='Test identity';b.onclick=()=>cb({credential:'fixture'});el.append(b)}}}}"}));
  await page.route("**/api/account/**",r=>{
    const route=new URL(r.request().url()).pathname.split("/").pop();
    if(route==="challenge")return r.fulfill({json:{nonce:"test",client_id:"test"}});
    if(route==="login")signed=r.request().postDataJSON().credential==="fixture";
    if(!signed)return r.fulfill({status:401,json:{detail:"Sign in required"}});
    if(route==="logout")signed=false;
    if(route==="training")merged=true;
    if(route==="hands" && r.request().method()==="POST"){
      stored=r.request().postDataJSON().hand;
      return r.fulfill({json:{id:"123"}});
    }
    if(route==="123")return r.fulfill({json:{id:"123",title:"Reviewed hand",hand:stored}});
    return r.fulfill({json:route==="me"?{name:"Test player"}:route==="observations"?{revision:0,archive:{entries:[],overrides:{},version:"1.0"}}:route==="hands"&&stored?[{id:"123",title:"Reviewed hand"}]:route==="training"?{added:0,duplicates:0}:[]});
  });
  await page.goto("/account");
  await page.getByRole("button",{name:"Sign in with Google"}).click();
  await page.getByRole("button",{name:"Test identity"}).click();
  await page.getByRole("button",{name:"Import Reviewed hand"}).click();
  expect(stored).toEqual(hand);
  await expect(page.getByRole("link",{name:"Open in Analyzer"})).toHaveAttribute("href","/analyzer?saved=123");
  await page.getByRole("link",{name:"Open in Analyzer"}).click();
  await expect(page.locator(".analyzer-table")).toContainText("BTN · QA reviewer");
  await page.goBack();
  await page.getByRole("button",{name:"Merge tab attempts"}).click();
  await expect(page.locator("main [role=status]")).toContainText("0 attempts saved");
  expect(merged).toBe(true);
  const download=page.waitForEvent("download");
  await page.getByRole("button",{name:"Export server evidence"}).click();
  expect((await download).suggestedFilename()).toBe("observations.json");
  await page.getByRole("button",{name:"Sign out"}).click();
  await expect(page.getByRole("heading",{name:"Guest workspace"})).toBeVisible();
});
