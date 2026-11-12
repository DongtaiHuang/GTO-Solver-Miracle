"use client";
import Link from "next/link";

import { practiceUrl } from "../lib/training";
import type { Hand } from "../lib/analyzer";

export function PracticeReview({
  source,
  scenario,
  combo,
  action,
  hand,
  index,
}: {
  source: string;
  scenario: string;
  combo: string;
  action: string;
  hand: Hand;
  index: number;
}) {
  async function review() {
    const identity = JSON.stringify([
      hand.trainer_hand_id ?? null,
      source,
      scenario,
      combo,
      index,
      action,
      hand.hero,
      hand.board,
      hand.actions.map((e) => [e.position, e.street, e.action, e.amount]),
      Object.keys(hand.seats)
        .sort()
        .map((k) => hand.seats[k as keyof Hand["seats"]].name),
    ]);
    const bytes = await crypto.subtle.digest(
      "SHA-256",
      new TextEncoder().encode(identity),
    );
    const id = Array.from(new Uint8Array(bytes).slice(0, 16), (b) =>
      b.toString(16).padStart(2, "0"),
    ).join("");
    const uuid = [
      id.slice(0, 8),
      id.slice(8, 12),
      id.slice(12, 16),
      id.slice(16, 20),
      id.slice(20),
    ].join("-");
    location.assign(practiceUrl(source, scenario, combo, action, uuid));
  }
  return (
    <p>
      <Link href={practiceUrl(source, scenario, combo)}>
        Practice Similar Spot
      </Link>{" "}
      ·{" "}
      <button onClick={() => void review()}>
        Review recorded action in Training Center
      </button>
    </p>
  );
}
