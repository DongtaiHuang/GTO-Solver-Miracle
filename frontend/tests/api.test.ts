import { expect, it, vi } from "vitest";
import { ApiError, requestGame } from "../lib/api";
import { gameState } from "./fixtures";
it("uses same-origin cookies and sends only the action payload", async () => {
  const mock = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify(gameState()))));
  vi.stubGlobal("fetch", mock);
  expect(await requestGame("/api/game")).toEqual(gameState());
  await requestGame("/api/game/actions", { action: "fold" });
  expect(mock).toHaveBeenLastCalledWith("/api/game/actions", expect.objectContaining({
    method: "POST", credentials: "same-origin", cache: "no-store", body: '{"action":"fold"}',
  }));
});
it("reports transport, API, and malformed response errors", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
  await expect(requestGame("/api/game")).rejects.toThrow("Connection lost");
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('{"detail":"Illegal action"}', { status: 400 })));
  await expect(requestGame("/api/game")).rejects.toMatchObject({ status: 400, message: "Illegal action" });
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("bad", { status: 502 })));
  await expect(requestGame("/api/game")).rejects.toThrow("could not be completed");
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("bad")));
  await expect(requestGame("/api/game")).rejects.toBeInstanceOf(ApiError);
});
