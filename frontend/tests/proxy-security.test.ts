import {afterEach,expect,it,vi} from "vitest";
import {NextRequest} from "next/server";
import {POST,GET} from "../app/api/[...path]/route";

afterEach(()=>vi.unstubAllGlobals());
it("forwards the browser origin through the fixed upstream and drops client forwarding headers",async()=>{
 const upstream=vi.fn().mockResolvedValue(new Response("{}",{status:401}));
 vi.stubGlobal("fetch",upstream);
 const req=new NextRequest("http://localhost/api/account/logout",{method:"POST",headers:{origin:"https://example.org","content-type":"application/json","x-forwarded-host":"example.org"},body:"{}"});
 const response=await POST(req,{params:Promise.resolve({path:["account","logout"]})});
 const [url,options]=upstream.mock.calls[0];
 expect(url).toBe((process.env.BACKEND_URL??"http://127.0.0.1:8000")+"/api/account/logout");
 expect(options.headers.get("origin")).toBe("https://example.org");
 expect(options.headers.has("x-forwarded-host")).toBe(false);
 expect(options.redirect).toBe("error");
 expect(response.headers.get("cache-control")).toContain("no-store");
});
it("only proxies listed routes",async()=>{
 const upstream=vi.fn();vi.stubGlobal("fetch",upstream);
 const res=await GET(new NextRequest("http://localhost/api/unlisted"),{params:Promise.resolve({path:["unlisted"]})});
 expect(res.status).toBe(404);expect(upstream).not.toHaveBeenCalled();
});
