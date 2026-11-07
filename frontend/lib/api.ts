import type { GameState } from "./types";
export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}
export async function requestJson<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      method: body === undefined ? "GET" : "POST", credentials: "same-origin", cache: "no-store", signal,
      headers: body === undefined ? {} : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch { throw new ApiError("Connection lost. Check that the backend is running and refresh the table.", 0); }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = typeof data?.detail === "string" ? data.detail :
      Array.isArray(data?.detail) && typeof data.detail[0]?.msg === "string" ? data.detail[0].msg : "The request could not be completed.";
    throw new ApiError(detail, response.status);
  }
  if (!data) throw new ApiError("The server returned an invalid response.", 502);
  return data as T;
}

export function requestGame(path: string, body?: unknown): Promise<GameState> {
  return requestJson<GameState>(path, body);
}
