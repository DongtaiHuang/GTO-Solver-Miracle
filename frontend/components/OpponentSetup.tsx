"use client";
import { useState, useEffect, useRef } from "react";
import type { OpponentProfile, ProfileConfig } from "../lib/study-types";
import { ProfileEditor } from "./ProfileEditor";
export const initialOpponents = (): ProfileConfig[] => ["tag", "lag", "tp", "lp", "tag"].map(
  id => ({ id: id as ProfileConfig["id"] }));
export function OpponentSetup({ profiles, configs, onChange, disabled }: {
  profiles: OpponentProfile[]; configs: ProfileConfig[]; onChange: (configs: ProfileConfig[]) => void; disabled: boolean;
}) {
  const [seat, setSeat] = useState(0);
  const drawer=useRef<HTMLDetailsElement>(null);
  useEffect(()=>{if(disabled && drawer.current) drawer.current.open=false;},[disabled]);
  return <details ref={drawer} className="opponent-setup"><summary>Opponent configuration
    <span>Five modeled opponents · configure before dealing</span></summary>
    <div className="seat-selectors" role="group" aria-label="Configure opponent seat">{configs.map((config, i) =>
      <button key={i} disabled={disabled} aria-pressed={i === seat} onClick={() => setSeat(i)} type="button">
        Seat {i + 1}<small>{profiles.find(p => p.id === config.id)?.name ?? config.id}</small></button>)}</div>
    <ProfileEditor compact profiles={profiles} value={configs[seat]} label={`Seat ${seat + 1} profile`} disabled={disabled}
      onChange={value => onChange(configs.map((item, i) => i === seat ? value : item))} />
    <p className="field-hint">Trainer opponents use heuristics. Standard GTO uses the fallback policy during play.
      These settings apply to the next hand; the active hand retains its own configuration.</p>
  </details>;
}
