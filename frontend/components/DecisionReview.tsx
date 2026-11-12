"use client";
import Link from "next/link";
import {useState} from "react";
import {requestJson} from "../lib/api";
import type {Event,Hand,Snapshot} from "../lib/analyzer";
import type {StrategyResult,StrategyScenarioIndex} from "../lib/strategy-types";
import type {ProfileId} from "../lib/study-types";
import type {EquityResult} from "../lib/equity-types";
import {PracticeReview} from "./PracticeReview";
import {MultiResponse} from "./MultiResponse";
import {RiverResponse} from "./RiverResponse";

export function DecisionReview({hand,state,recorded}:{hand:Hand;state:Snapshot;recorded?:Event}){
 const [range,setRange]=useState(""),[equity,setEquity]=useState(""),[err,setErr]=useState("");
 const [strategy,setStrategy]=useState<StrategyResult|null>(null),[profile,setProfile]=useState<ProfileId>("tag");
 const [busy,setBusy]=useState(false);
 async function run(fn:()=>Promise<void>){setBusy(true);setErr("");try{await fn();}catch(e){setErr(String(e));}finally{setBusy(false);}}
 const hero=state.players[hand.hero],actor=state.actor?state.players[state.actor]:null;
 const combo=strategy?.combinations.find(c=>c.cards.slice().sort().join()===actor?.cards?.slice().sort().join());
 const actionKey=recorded ? recorded.action+(recorded.amount===null?"":"@"+recorded.amount) : "";
 const evMap=combo?.action_ev;
 const completeEV=evMap && strategy?.actions.every(a=>evMap[a.key]!==undefined);
 return <fieldset className="study-card" disabled={busy}><legend>Decision analysis</legend>
 <p>Call pot odds {state.odds===null?"unavailable":(100*state.odds).toFixed(1)+"%"} · Required call {state.legal.to_call} chips</p>
 <p>{state.board.length?"Board texture: "+(state.texture.paired?"paired":"unpaired")+", maximum "+state.texture.max_suit_count+" of one suit.":"Preflop · no board texture"}</p>
 <label className="field">Heads-up equity assumption<select value={range} onChange={e=>{setRange(e.target.value);setEquity("");}}>
 <option value="">Choose opponent range</option>{["AA KK QQ AKs","22 33 44 55 66","AKs AKo AQs AQo","AA"].map(r=><option key={r}>{r}</option>)}</select></label>
 <button disabled={!hero.cards||!range||!state.board_complete} onClick={()=>void run(async()=>{
 const result=await requestJson<EquityResult>("/api/equity/hand-vs-range",{hero_cards:hero.cards,board:state.board,
 opponent_range:{weights:Object.fromEntries(range.split(" ").map(h=>[h,100]))},method:"auto",samples:2000,seed:42});
 setEquity((result.players[0].equity*100).toFixed(2)+"% showdown equity · "+result.method);
 })}>Calculate hero equity</button><p>{equity}</p>
 <label className="field">Opponent model<select aria-label="Opponent model" value={profile} onChange={e=>setProfile(e.target.value as ProfileId)}>
 {["standard_gto","tag","lag","tp","lp"].map(p=><option key={p} value={p}>{p.toUpperCase()}</option>)}</select></label>
 {state.candidates.length?<label className="field">Analyze under these solver ranges and tree
 <select defaultValue="" onChange={e=>{const id=e.target.value;setStrategy(null);if(id)void run(async()=>{
 const index=await requestJson<StrategyScenarioIndex>("/api/strategy/scenarios");
 const chosen=index.scenarios.find(v=>v.solution_id===id);if(!chosen)throw Error("Scenario no longer available");
 setStrategy(await requestJson<StrategyResult>("/api/strategy/query",{scenario:chosen.scenario}));
 });}}><option value="">Choose exact abstraction</option>{state.candidates.map(s=><option key={s}>{s}</option>)}</select></label>:
 <p>Solver strategy unavailable for this scenario</p>}
 {strategy&&<>{strategy.status==="available"&&strategy.source&&<Link className="button-link" href={`/?source=${encodeURIComponent(strategy.source.solution_id)}&scenario=${strategy.scenario_id}`}>Inspect this decision in Study</Link>}<p>{strategy.scenario.abstraction.assumptions.join(" ")}</p>
 <p>{strategy.source?.validation_methodology}</p>{combo?<ul>{Object.entries(combo.frequencies).map(([a,f])=><li key={a}>{a}: {(100*f).toFixed(1)}% · EV {combo.action_ev?.[a]?.toFixed(2)??"unavailable"} chips</li>)}</ul>:
 <><p>Acting hand unknown or outside the represented range. Reach-weighted source range:</p>
 <ul>{Object.entries(strategy.frequencies??{}).map(([a,f])=><li key={a}>{a} {(100*f).toFixed(1)}% · EV {strategy.action_ev?.[a]?.toFixed(2)??"unavailable"} chips</li>)}</ul></>}
 {recorded&&combo&&state.actor===hand.hero&&strategy.status==="available"&&strategy.source&&<PracticeReview source={strategy.source.solution_id} scenario={strategy.scenario_id} combo={combo.cards.join("")} action={actionKey} hand={hand} index={hand.actions.indexOf(recorded)}/>}
 {recorded&&<p>{evMap&&completeEV&&evMap[actionKey]!==undefined ?
 "Recorded action "+actionKey+" costs "+(Math.max(...Object.values(evMap))-evMap[actionKey]).toFixed(2)+" chips versus the highest action EV in this tree." :
 "Individual EV loss unavailable for this hand and recorded action."}</p>}
 {strategy.status==="available"&&strategy.source?.solution_id.startsWith("ts-")&&<MultiResponse key={strategy.scenario_id+profile} strategy={strategy} profile={profile} combos={combo?[combo.cards.join("")]:actor?.cards?[]:undefined}/>}
 {strategy.source?.solution_id.startsWith("river-")&&(combo||!actor?.cards)&&<RiverResponse key={profile+strategy.scenario_id} scenario={strategy.scenario} profile={profile} heroCombo={combo?.cards.join("")}/>}</>}
 {err&&<p role="alert">{err}</p>}</fieldset>
}
