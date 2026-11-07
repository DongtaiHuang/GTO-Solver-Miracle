import { NextRequest } from "next/server";
import { expect, it, vi } from "vitest";
import { GET, POST } from "../app/api/[...path]/route";
it("forwards the session cookie and action and relays the private response", async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response('{"ok":true}', {
    headers: { "set-cookie": "poker_session=opaque; HttpOnly; Path=/api; SameSite=Strict" },
  }));
  vi.stubGlobal("fetch", fetchMock);
  const response = await POST(new NextRequest("http://localhost:3000/api/game/actions", {
    method: "POST", headers: { "Content-Type": "application/json", cookie: "poker_session=opaque",
      origin: "http://localhost:3000" }, body: '{"action":"check"}',
  }), { params: Promise.resolve({ path: ["game", "actions"] }) });
  expect(response.status).toBe(200);
  expect(response.headers.get("set-cookie")).toContain("HttpOnly");
  expect(response.headers.get("cache-control")).toContain("no-store");
  const [url, options] = fetchMock.mock.calls[0];
  expect(url).toBe("http://127.0.0.1:8000/api/game/actions");
  expect(options.headers.get("cookie")).toBe("poker_session=opaque");
  expect(options.headers.get("origin")).toBe("http://localhost:3000");
  expect(options.body).toBe('{"action":"check"}');
});
it("rejects routes outside the trainer API without forwarding", async () => {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  const response = await GET(new NextRequest("http://localhost:3000/api/admin"),
    { params: Promise.resolve({ path: ["admin"] }) });
  expect(response.status).toBe(404);
  expect(fetchMock).not.toHaveBeenCalled();
});
it("handles unavailable backends and relays validation errors", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  const unavailable = await GET(new NextRequest("http://localhost:3000/api/game"),
    { params: Promise.resolve({ path: ["game"] }) });
  expect(unavailable.status).toBe(502);
  expect(await unavailable.json()).toEqual({ detail: "Backend unavailable. Please try again." });
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('{"detail":"Illegal action"}', { status: 400 })));
  const error = await POST(new NextRequest("http://localhost:3000/api/games", { method: "POST", body: "{}" }),
    { params: Promise.resolve({ path: ["games"] }) });
  expect(error.status).toBe(400);
  expect(await error.json()).toEqual({ detail: "Illegal action" });
});
