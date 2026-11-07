"use client";
import { useState } from "react";
import type { Action, LegalActions } from "../lib/types";
import { chips } from "./PlayerSeat";
export function ActionControls({ legal, disabled, onAction }: {
  legal: LegalActions; disabled: boolean; onAction: (action: Action, amount?: number) => void;
}) {
  const [amount, setAmount] = useState(String(legal.min_raise_to ?? ""));
  const aggressive = legal.actions.includes("bet") ? "bet" : legal.actions.includes("raise") ? "raise" : null;
  const value = Number(amount);
  const valid = amount.trim() !== "" && Number.isSafeInteger(value) &&
    legal.min_raise_to !== null && value >= legal.min_raise_to && value <= legal.max_raise_to;
  return <section className="action-controls" aria-label="Your actions">
    <div className="action-heading"><h2>Your decision</h2><span>{legal.to_call ? `${chips(legal.to_call)} to call` : "No bet to call"}</span></div>
    {aggressive && <div className="sizing">
      <div className="presets" aria-label="Pot size presets">
        {Object.entries(legal.presets).map(([label, target]) => <button key={label} disabled={disabled}
          title={`Total street bet: ${target} chips`} onClick={() => setAmount(String(target))}>{label}% pot</button>)}
      </div>
      <label className="size-input">Total street bet (chips)
        <input aria-label="Total street bet (chips)" type="number" step="1"
          min={legal.min_raise_to ?? 0} max={legal.max_raise_to} value={amount}
          disabled={disabled} onChange={e => setAmount(e.target.value)} />
      </label>
      <p className="size-hint">Raise-to sizing · minimum {chips(legal.min_raise_to ?? 0)} · maximum {chips(legal.max_raise_to)}</p>
    </div>}
    <div className="action-buttons">
      <button className="fold" disabled={disabled || !legal.actions.includes("fold")} onClick={() => onAction("fold")}>Fold</button>
      {legal.actions.includes("check") && <button disabled={disabled} onClick={() => onAction("check")}>Check</button>}
      {legal.actions.includes("call") && <button disabled={disabled} onClick={() => onAction("call")}>Call {chips(legal.to_call)}</button>}
      {aggressive && <button className="primary" disabled={disabled || !valid}
        onClick={() => onAction(aggressive, value)}>{aggressive === "bet" ? "Bet" : "Raise to"} {valid ? chips(value) : ""}</button>}
      <button className="all-in" disabled={disabled || !legal.actions.includes("all_in")} onClick={() => onAction("all_in")}>All-in</button>
    </div>
  </section>;
}
