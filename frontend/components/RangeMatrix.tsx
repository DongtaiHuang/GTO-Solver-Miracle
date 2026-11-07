"use client";
import type { CSSProperties } from "react";
import { rangeMatrix } from "../lib/ranges";
export function RangeMatrix({ weights, selected, onSelect }: {
  weights: Record<string, number>; selected: string; onSelect: (hand: string) => void;
}) {
  return <div className="range-matrix" role="group" aria-label="169 starting hand classes">
    {rangeMatrix.map((row, i) => row.map((hand, j) => <button key={hand} type="button"
      className={`range-cell ${i === j ? "range-pair" : i < j ? "range-suited" : "range-offsuit"} ${selected === hand ? "range-focused" : ""}`}
      style={{ "--range-weight": `${weights[hand] ?? 0}%` } as CSSProperties}
      aria-label={`${hand} inclusion ${weights[hand] ?? 0}%`} aria-pressed={(weights[hand] ?? 0) > 0}
      onClick={() => onSelect(hand)}><span>{hand}</span></button>))}
  </div>;
}
