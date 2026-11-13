import {expect,it,vi} from "vitest";
import {readHistory} from "../lib/analyzer";
it("explains an invalid field without echoing imported values",async()=>{
  vi.stubGlobal("fetch",vi.fn().mockResolvedValue(Response.json({detail:[{loc:["body","version"],input:"private sample"}]},{status:422})));
  await expect(readHistory("{}")).rejects.toThrow(/^Invalid hand history \(version\)\. Check the hand format and recorded actions\.$/);
});
