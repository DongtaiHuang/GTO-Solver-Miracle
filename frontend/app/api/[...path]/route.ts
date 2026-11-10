import { NextRequest, NextResponse } from "next/server";
async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const route = path.join("/");
  const permitted = (request.method === "GET" && ["game", "profiles", "study/current", "strategy/scenarios", "strategy/examples"].includes(route)) ||
    (request.method === "POST" && ["games", "game/actions", "study", "equity/hand-vs-hand", "equity/hand-vs-range",
      "equity/range-vs-range", "equity/multiway", "equity/pot-odds",
      "strategy/query", "strategy/frequencies", "strategy/source"].includes(route));
  if (!permitted) return NextResponse.json({ detail: "Not found" }, { status: 404 });
  try {
    const headers = new Headers();
    for (const name of ["cookie", "content-type", "origin"]) {
      const value = request.headers.get(name);
      if (value) headers.set(name, value);
    }
    const body = request.method === "POST" ? await request.text() : undefined;
    const response = await fetch(`${process.env.BACKEND_URL ?? "http://127.0.0.1:8000"}/api/${route}`, {
      method: request.method, headers, body, cache: "no-store", redirect: "error",
      signal: AbortSignal.timeout(route.startsWith("equity/") ? 30000 : 15000),
    });
    const result = new NextResponse(await response.text(), { status: response.status });
    result.headers.set("Content-Type", "application/json");
    result.headers.set("Cache-Control", "no-store, private");
    result.headers.set("Vary", "Cookie");
    const cookie = response.headers.get("set-cookie");
    if (cookie) result.headers.set("set-cookie", cookie);
    return result;
  } catch {
    return NextResponse.json({ detail: "Backend unavailable. Please try again." },
      { status: 502, headers: { "Cache-Control": "no-store" } });
  }
}
export const GET = proxy;
export const POST = proxy;
