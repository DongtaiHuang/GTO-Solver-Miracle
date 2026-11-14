import { NextRequest, NextResponse } from "next/server";
async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const route = path.join("/");
  const permitted = (request.method === "GET" && ["health","strategy/training/exercises","analyzer/trainer","game", "profiles", "study/current", "strategy/scenarios", "strategy/examples"].includes(route)) ||
    (request.method === "POST" && ["strategy/training/grade","strategy/training/report","observations/report","analyzer/replay","games", "game/actions", "study", "equity/hand-vs-hand", "equity/hand-vs-range",
      "equity/range-vs-range", "equity/multiway", "equity/pot-odds",
      "strategy/multistreet-policy","strategy/multistreet","strategy/exploit", "strategy/query", "strategy/frequencies", "strategy/source"].includes(route));
  const accountRoutes=request.method==="GET"
    ? /^account\/(me|observations|hands(?:\/[0-9a-f-]{36})?|sessions(?:\/[0-9a-f-]{36})?)$/
    : /^account\/(challenge|login|logout|delete|observations|training(?:\/clear)?|hands|hands\/[0-9a-f-]{36}\/(update|delete)|(?:sessions|attempts)\/[0-9a-f-]{36}\/delete)$/;
  const account=process.env.NEXT_PUBLIC_GUEST_DEMO!=="true" && accountRoutes.test(route);
  if (!permitted && !account) return NextResponse.json({ detail: "Not found" }, { status: 404 });
  try {
    const headers = new Headers();
    for (const name of ["cookie", "content-type", "origin"]) {
      const value = request.headers.get(name);
      if (value) headers.set(name, value);
    }
    let body: string | undefined;
    if(request.method==="POST"){
      const limit = route.startsWith("strategy/") ? 2*1024*1024 : 1024*1024;
      const reader=request.body?.getReader();
      const chunks:Uint8Array<ArrayBufferLike>[]=[];let size=0;
      if(reader){while(true){const chunk=await reader.read();if(chunk.done)break;
        size+=chunk.value.byteLength;if(size>limit){await reader.cancel();return NextResponse.json({detail:"Archive too large"},{status:413});}chunks.push(chunk.value);}}
      const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.length;}
      body=new TextDecoder("utf-8",{fatal:true}).decode(bytes);
    }
    const response = await fetch(`${process.env.BACKEND_URL ?? "http://127.0.0.1:8000"}/${route==="health"?"health":"api/"+route}${account?request.nextUrl.search:""}`, {
      method: request.method, headers, body, cache: "no-store", redirect: "error",
      signal: AbortSignal.timeout(route.startsWith("equity/") ? 30000 : 15000),
    });
    const result = new NextResponse(await response.text(), { status: response.status });
    result.headers.set("Content-Type", "application/json");
    result.headers.set("Cache-Control", "no-store, private");
    result.headers.set("Vary", "Cookie");
    for(const cookie of response.headers.getSetCookie())result.headers.append("set-cookie",cookie);
    return result;
  } catch {
    return NextResponse.json({ detail: "Backend unavailable. Please try again." },
      { status: 502, headers: { "Cache-Control": "no-store" } });
  }
}
export const GET = proxy;
export const POST = proxy;
