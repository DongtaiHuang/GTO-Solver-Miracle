import {expect,test} from "@playwright/test";

for(const width of [390,768,1440]){
  test("all workspace destinations remain accessible at "+width+"px",async({page})=>{
    await page.setViewportSize({width,height:900});
    await page.goto("/");
    const nav=page.getByRole("navigation",{name:"Main navigation"});
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link",{name:"Skip to workspace"})).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.locator("#workspace-content")).toBeFocused();
    for(const [label,path] of [["Trainer","/trainer"],["Hand Analyzer","/analyzer"],["Training Center","/training"],["Player Account","/account"],["Study","/"]]){
      const link=nav.getByRole("link",{name:new RegExp("^"+label)});
      await link.click();
      await expect(page).toHaveURL(url=>url.pathname===path);
      await expect(link).toHaveAttribute("aria-current","page");
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    }
    await page.goBack();
    await expect(nav.getByRole("link",{name:/^Player Account/})).toHaveAttribute("aria-current","page");
    await page.goForward();
    await expect(nav.getByRole("link",{name:/^Study/})).toHaveAttribute("aria-current","page");
  });
}
