"use client";
import type { OpponentProfile, ProfileConfig } from "../lib/study-types";
import { parameterLabels } from "../lib/study-types";
export function ProfileEditor({ profiles, value, onChange, label = "Opponent profile", disabled = false }: {
  profiles: OpponentProfile[]; value: ProfileConfig; onChange: (value: ProfileConfig) => void;
  label?: string; disabled?: boolean;
}) {
  const selected = profiles.find(p => p.id === value.id);
  const parameters = value.parameters ?? selected?.parameters;
  return <section className="profile-editor">
    <label className="field">{label}<select aria-label={label} value={value.id} disabled={disabled}
      onChange={event => { const profile = profiles.find(p => p.id === event.target.value);
        if (profile) onChange({ id: profile.id, parameters: profile.parameters ? { ...profile.parameters } : null });
      }}>{profiles.map(profile => <option key={profile.id} value={profile.id}>{profile.name}</option>)}</select></label>
    <p className="profile-description">{selected?.description ?? "Loading profile definitions…"}</p>
    <span className="availability-tag">{value.id === "standard_gto" ? "Not yet solver-backed" : "Editable modeling assumptions"}</span>
    {parameters ? <>
      <div className="parameter-grid">{Object.entries(parameterLabels).map(([key, title]) =>
        <label className="field" key={key}>{title} (%)
          <input type="number" min="0" max="100" step="1" value={parameters[key as keyof typeof parameters]}
            disabled={disabled} onChange={event => onChange({ id: value.id, parameters: {
              ...parameters, [key]: Number(event.target.value),
            } })} />
        </label>)}</div>
      <p className="field-hint">Illustrative defaults, not measured statistics. PFR must not exceed VPIP.
        Tendency parameters tune heuristic behavior.</p>
    </> : <p className="field-hint">GTO solution unavailable. Select an archetype to edit assumed statistics.
      Trainer uses the original random heuristic as a fallback for Standard GTO.</p>}
    <button className="text-button" type="button" disabled={disabled || !selected}
      onClick={() => selected && onChange({ id: selected.id,
        parameters: selected.parameters ? { ...selected.parameters } : null })}>Reset profile defaults</button>
  </section>;
}
