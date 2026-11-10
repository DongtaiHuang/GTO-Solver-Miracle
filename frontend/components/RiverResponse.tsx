"use client";
import { useEffect, useState } from "react";
import { requestJson } from "../lib/api";
import type { StrategyScenario } from "../lib/strategy-types";
import type { ProfileId } from "../lib/study-types";

type Rates = Record<string,number>;
interface Decision {
  combo:string; baseline:Rates; equilibrium_action_ev:Rates; response:Rates; model_action_ev:Rates;
  baseline_ev:number; response_ev:number; gain:number; equilibrium_cost:number;
}
interface Analysis {opponent: Record<string,Rates>; decisions:Decision[]; message:string}
const chips = (v:number) => v.toFixed(2);
const percent = (v:number) => (100*v).toFixed(1)+"%";

export function RiverResponse({scenario,profile,heroCombo}:{scenario:StrategyScenario;profile:ProfileId;heroCombo?:string}) {
  const [overrides,setOverrides] = useState<Rates>({});
  const [data,setData] = useState<Analysis|null>(null);
  const [error,setError] = useState("");
  const [busy,setBusy] = useState(false);
  useEffect(()=>{
    const controller = new AbortController();
    setBusy(true); setError("");
    requestJson<Analysis>("/api/strategy/exploit",{scenario,profile,overrides},controller.signal)
      .then(result=>{if(!controller.signal.aborted)setData(result);})
      .catch(err=>{if(!controller.signal.aborted){setData(null);setError(err.message);}})
      .finally(()=>{if(!controller.signal.aborted)setBusy(false);});
    return ()=>controller.abort();
  },[scenario,profile,overrides]);
  return <section className="study-card" aria-label="Model-conditioned river response">
    <h2>Model-conditioned river response</h2>
    <p>{profile==="standard_gto"?"Opponent uses the reviewed equilibrium policy.":"Edit the opponent’s river probabilities. Other legal responses receive the remaining probability."}</p>
    {error && <p role="alert">{error}</p>}
    {data && Object.entries(data.opponent).map(([combo,policy])=>{
      const active=Object.keys(policy).find(a=>a.startsWith("bet@")||a.startsWith("call@"))!;
      return <div key={combo}><label className="field">{combo} {active} (%)
        <input type="number" min="0" max="100" step="any" disabled={profile==="standard_gto"}
          value={Number(((overrides[combo]??policy[active])*100).toFixed(6))}
          onChange={e=>{const value=e.currentTarget.valueAsNumber;if(value>=0&&value<=100)setOverrides(prev=>({...prev,[combo]:value/100}));}}/></label>
        <small>{Object.entries(policy).map(([a,v])=>a+" "+percent(v)).join(" · ")}</small></div>;
    })}
    {busy?<p>Calculating…</p>:data && <><p>{data.message}</p>
      {data.decisions.filter(d=>!heroCombo||d.combo===heroCombo).map(d=><section key={d.combo}>
        <h3>{d.combo}</h3><div className="strategy-comparison"><div><h4>GTO baseline</h4>
        {Object.entries(d.baseline).map(([a,v])=><p key={a}>{a} {percent(v)} · equilibrium action EV {chips(d.equilibrium_action_ev[a])}</p>)}
        <b>EV against model {chips(d.baseline_ev)}</b></div><div><h4>Best response</h4>
        {Object.entries(d.response).map(([a,v])=><p key={a}>{a} {percent(v)} · action EV {chips(d.model_action_ev[a])}</p>)}
        <b>EV against model {chips(d.response_ev)}</b></div></div>
        <p>{d.gain>1e-8 ? 'Changing the action mix increases expected return against these opponent probabilities.' : 'The baseline mix already attains the best response EV for these probabilities.'}</p>
        <p>Gain against model {chips(d.gain)} chips · Cost against equilibrium {chips(d.equilibrium_cost)} chips</p>
      </section>)}</>}
  </section>;
}
