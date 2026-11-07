"use client";
import { useEffect, useState } from "react";
import { requestJson } from "./api";
import type { OpponentProfile } from "./study-types";
export function useProfiles() {
  const [profiles, setProfiles] = useState<OpponentProfile[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    requestJson<OpponentProfile[]>("/api/profiles", undefined, controller.signal).then(setProfiles).catch(err => {
      if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "Profiles unavailable");
    });
    return () => controller.abort();
  }, []);
  return { profiles, error };
}
