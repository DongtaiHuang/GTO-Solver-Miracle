import type { OpponentProfile, ProfileConfig } from "../lib/study-types";
import { parameterLabels } from "../lib/study-types";
import type { StrategyResult } from "../lib/strategy-types";
import { FrequencyChart } from "./StrategyMatrix";
import { ProfileEditor } from "./ProfileEditor";

export function StrategyComparison({ result, profiles, opponent, onChange }: {
  result: StrategyResult | null; profiles: OpponentProfile[]; opponent: ProfileConfig;
  onChange: (value: ProfileConfig) => void;
}) {
  const current = profiles.find(p => p.id === opponent.id);
  const params = opponent.parameters ?? current?.parameters;
  const demo = result?.status === "synthetic_demo";
  return <section className="strategy-comparison" aria-label="GTO versus opponent comparison">
    <div className="study-card"><div className="card-heading"><h2>GTO baseline</h2>
      <span className={`data-tag ${demo ? "unavailable" : result?.status === "available" ? "calculated" : "unavailable"}`}>
        {demo ? "SYNTHETIC DEMO ONLY" : result?.status === "available" ? "REVIEWED SOLVER DATA" : "UNAVAILABLE"}</span></div>
      {demo && <p className="demo-warning">Synthetic frequencies below are UI examples. No real GTO baseline is available for this example.</p>}
      <FrequencyChart frequencies={result?.frequencies ?? null} actions={result?.actions ?? []}
        label={demo ? "Synthetic baseline demonstration" : "Baseline action distribution"} />
      <p className="field-hint">Aggregate uses only represented combos and dataset reach weights.
        {result?.source ? ` Source: ${result.source.solver_identifier} ${result.source.solver_version}.` : " No exact permitted source matched."}</p>
      <p className="field-hint">Source metadata and local approval are not an independent proof of equilibrium.</p>
    </div>
    <div className="study-card"><div className="card-heading"><h2>{current?.name ?? "Opponent model"}</h2><span className="data-tag modeled">ASSUMPTIONS</span></div>
      <p>{current?.description ?? "Select an opponent profile."}</p>
      <p className="comparison-boundary">These are modeled parameters, not solver action frequencies.
        {result?.status==="available" && /^river-(275|550)-(btn|bb)-v1$/.test(result.source?.solution_id??"")
          ? "The river response below uses separate, combo-specific river assumptions."
          : result?.status==="available" && result.source?.solution_id.startsWith("ts-") ? "Select a conditional policy below to calculate a full-tree response." : "No exploitative best response, expected profit, or opponent-specific optimal EV has been calculated."}</p>
      <details><summary>Edit opponent assumptions</summary>
      {params ? <dl className="model-parameter-summary">{Object.entries(parameterLabels).map(([key,label]) =>
        <div key={key}><dt>{label}</dt><dd>{params[key as keyof typeof params]}%</dd></div>)}</dl> :
        <p>{result?.status==="available" && /^river-(275|550)-(btn|bb)-v1$/.test(result.source?.solution_id??"")
          ? "Standard GTO uses the paired equilibrium combo policy at this river decision."
          : result?.status==="available" && result.source?.solution_id.startsWith("ts-") ? "Standard GTO uses the complete Task 009 equilibrium reference." : "Standard GTO is not yet solver-backed. No statistical parameters or opponent action frequencies are invented."}</p>}
        <ProfileEditor profiles={profiles} value={opponent} onChange={onChange} /></details>
    </div>
  </section>;
}
