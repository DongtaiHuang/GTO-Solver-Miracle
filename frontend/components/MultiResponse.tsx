"use client";
import {useEffect,useState} from "react";
import {StrategyMatrix} from "./StrategyMatrix";
import {requestJson} from "../lib/api";
import type {StrategyResult} from "../lib/strategy-types";
import type {ProfileId} from "../lib/study-types";

type Rates=Record<string,number>;
type Editor=Record<string,Record<string,Rates>>;
interface Edit {node:string;combo:string;probabilities:Rates}
interface Choice {reach:number; frequencies:Rates;action_ev:Rates;ev:number}
interface Decision {combo:string;baseline_equilibrium:Choice|null;baseline_model:Choice|null;response_model:Choice|null;
 response_equilibrium:Choice|null;gain:number|null;equilibrium_cost:number|null}
interface Result {name:string;changes:{node:string;combo:string;equilibrium:Rates;modeled:Rates}[];
 root:{equilibrium_ev:number;baseline_model_ev:number;response_model_ev:number;gain:number;equilibrium_cost:number};
 decisions:Decision[]}
interface Report {assumptions:string;results:Result[]}
const fmt=(v:number|null)=>v===null?"Unreachable":v.toFixed(3);
const rates=(values:Rates)=>Object.entries(values).map(([k,v])=>k+" "+(100*v).toFixed(1)+"%").join(" · ");
const defaults={tag:40,lag:75,tp:15,lp:25,standard_gto:0};
export function MultiResponse({strategy,profile,combos,selection}:{strategy:StrategyResult;profile:ProfileId;combos?:string[];selection?:{hand:string;select:(hand:string)=>void}}){
 const [bet,setBet]=useState(defaults[profile]),[sensitivity,setSensitivity]=useState(false);
 const [editor,setEditor]=useState<Editor>({}),[node,setNode]=useState(""),[combo,setCombo]=useState("");
 const [percent,setPercent]=useState("50"),[edits,setEdits]=useState<Edit[]>([]),[data,setData]=useState<Report|null>(null);
 const [error,setError]=useState(""),[busy,setBusy]=useState(false);
 const context={reference_version:"ts009-average-1500-v1",solution_id:strategy.source?.solution_id,
   scenario:strategy.scenario,opponent:strategy.scenario.opponent_position};
 useEffect(()=>{
   const c=new AbortController();
   requestJson<Editor>("/api/strategy/multistreet-policy",context,c.signal).then(rows=>{
     if(c.signal.aborted)return;
     setEditor(rows);const first=Object.keys(rows)[0];setNode(first);setCombo(Object.keys(rows[first])[0]);
   }).catch(e=>{if(!c.signal.aborted)setError(e.message);});
   return ()=>c.abort();
 },[strategy]);
 const equilibrium=editor[node]?.[combo];
 function changeNode(n:string){setNode(n);setCombo(Object.keys(editor[n])[0]);}
 function override(){
   if(!equilibrium||percent===""||Number(percent)<0||Number(percent)>100)return;
   const [a,b]=Object.keys(equilibrium);const prob=Number(percent)/100;
   setEdits(old=>[...old.filter(e=>e.node!==node||e.combo!==combo),{node,combo,probabilities:{[a]:1-prob,[b]:prob}}]);
   setData(null);
 }
 async function calculate(){
   setBusy(true);setError("");setData(null);
   const hypotheses=profile==="standard_gto"?[{name:"Equilibrium benchmark",profile}]:
    (sensitivity?[["Base",bet],["Lower opening bet",Math.max(0,bet-15)],["Higher opening bet",Math.min(100,bet+15)]]:[[ "Base",bet]])
     .map(([name,p])=>({name,profile,opening_bet:Number(p)/100,overrides:edits}));
   try{setData(await requestJson<Report>("/api/strategy/multistreet",{...context,hypotheses}));}
   catch(e){setError(String(e));}finally{setBusy(false);}
 }
 const base=data?.results[0];
 const responseClasses=strategy.classes.flatMap(c=>{
   const keys=new Set(strategy.combinations.filter(v=>v.hand_class===c.hand_class).map(v=>v.cards.join("")));
   const rows=(base?.decisions??[]).filter(d=>keys.has(d.combo)).flatMap(d=>d.response_model?[d.response_model]:[]);
   const mass=rows.reduce((n,row)=>n+row.reach,0);
   if(!mass)return [];
   const frequencies=Object.fromEntries(strategy.actions.map(a=>[a.key,rows.reduce((n,row)=>n+row.reach*(row.frequencies[a.key]??0),0)/mass]));
   return [{...c,frequencies,reach_mass:mass,represented_combos:rows.length,action_ev:null}];
 });
 return <fieldset className="study-card" disabled={busy} aria-label="Multi-street response"><legend>Turn-to-river response</legend>
 <p>{context.opponent} policy · {profile.toUpperCase()} · Unedited rows inherit the complete 1,500-iteration equilibrium reference.</p>
 {profile!=="standard_gto"&&<><label className="field">Opening turn bet (%)<input type="number" min="0" max="100" value={bet}
 onChange={e=>{const v=e.currentTarget.valueAsNumber;if(v>=0&&v<=100){setBet(v);setData(null);}}}/></label>
 <p>Illustrative bet rate across all opponent combos on their first checked-to or unopened turn decision.</p>
 <label><input type="checkbox" checked={sensitivity} onChange={e=>{setSensitivity(e.target.checked);setData(null);}}/> Compare opening rates ±15 percentage points (bounded 0–100%)</label></>}
 <details><summary>Inspect equilibrium rows and edit individual assumptions</summary>
 {node&&<><label className="field">Opponent public history<select aria-label="Opponent public history" value={node} onChange={e=>changeNode(e.target.value)}>{Object.keys(editor).map(k=><option key={k}>{k}</option>)}</select></label>
 <label className="field">Opponent combo<select aria-label="Opponent combo" value={combo} onChange={e=>setCombo(e.target.value)}>{Object.keys(editor[node]).map(k=><option key={k}>{k}</option>)}</select></label>
 <p>Equilibrium: {equilibrium&&rates(equilibrium)}</p>
 {profile!=="standard_gto"&&equilibrium&&<><label className="field">{Object.keys(equilibrium)[1]} override (%)<input type="number" min="0" max="100" value={percent} onChange={e=>setPercent(e.target.value)}/></label>
 <button disabled={edits.length>=32&&!edits.some(e=>e.node===node&&e.combo===combo)} onClick={override}>Apply combo override</button></>}
 {edits.map(row=><p key={row.node+row.combo}>{row.node} {row.combo} · {rates(row.probabilities)} <button onClick={()=>{
 setEdits(old=>old.filter(e=>e!==row));setData(null);}}>Remove override</button></p>)}</>}</details>
 <button onClick={()=>void calculate()}>{busy?"Calculating…":"Calculate full-tree response"}</button>
 {error&&<p role="alert">{error}</p>}
 {data&&<><p>{data.assumptions}</p>{selection&&<details><summary>Base model · best-response matrix</summary>
 <StrategyMatrix classes={responseClasses} actions={strategy.actions} selected={selection.hand} onSelect={selection.select} demo={false} label="Model-conditioned best-response matrix"/></details>}{data.results.length>1 && base && <details open><summary>Sensitivity at the selected decision</summary>
 {base.decisions.filter(d=>!combos||combos.includes(d.combo)).map(d=>{
   const alternatives=data.results.map(r=>{
     const decision=r.decisions.find(v=>v.combo===d.combo);
     const actions=decision?.response_model?Object.entries(decision.response_model.frequencies).filter(([,v])=>v>0).map(([a])=>a).join(" / "):"Unreachable";
     return {name:r.name,actions,gain:fmt(decision?.gain??null)};
   });
   return <p key={d.combo}><b>{d.combo} · {new Set(alternatives.map(a=>a.actions)).size>1?"Response actions or reach change":"Same response actions"}</b><br/>
   {alternatives.map(a=>a.name+": "+a.actions+" (gain "+a.gain+")").join(" · ")}</p>;
 })}
 </details>}{data.results.map(result=><section key={result.name}><h3>{result.name} · root EV (chips)</h3>
 <p>Equilibrium against equilibrium {fmt(result.root.equilibrium_ev)} · Baseline against model {fmt(result.root.baseline_model_ev)} · Best response against model {fmt(result.root.response_model_ev)}</p>
 <p><b>Root gain {fmt(result.root.gain)}</b> · Cost against equilibrium {fmt(result.root.equilibrium_cost)}</p>
 <h4>Selected decision · conditional chips</h4>
 {result.decisions.filter(d=>!combos||combos.includes(d.combo)).map(d=><div key={d.combo}><b>{d.combo}</b>
 {d.response_model && context.solution_id && <a className="button-link" href={"/training?"+new URLSearchParams({
   source:context.solution_id,scenario:strategy.scenario_id,combo:d.combo,policy:JSON.stringify(profile==="standard_gto"?{name:result.name,profile}:{
     name:result.name,profile,opening_bet:Math.max(0,Math.min(100,bet+(result.name==="Lower opening bet"?-15:result.name==="Higher opening bet"?15:0)))/100,overrides:edits})
 })}>Practice against this hypothesis</a>}
 <p>Baseline against model: {d.baseline_model?rates(d.baseline_model.frequencies)+" · EV "+fmt(d.baseline_model.ev):"Unreachable"}</p>
 <p>Best response: {d.response_model?rates(d.response_model.frequencies)+" · EV "+fmt(d.response_model.ev):"Unreachable"}</p>
 <p>Conditional gain {fmt(d.gain)} · equilibrium cost {fmt(d.equilibrium_cost)}</p>
 <details><summary>Action EVs and decision reach</summary>{[["Baseline",d.baseline_model],["Response",d.response_model]].map(([label,choice])=>{
 const row=choice as Choice|null;return <p key={String(label)}>{String(label)}: {row?Object.entries(row.action_ev).map(([a,v])=>a+" "+fmt(v)).join(" · ")+" · joint reach "+row.reach.toPrecision(4):"Unreachable"}</p>;})}</details></div>)}
 {combos?.length===0&&<p>No covered combination selected.</p>}
 <details><summary>Policy changes ({result.changes.length})</summary>{result.changes.map(c=><p key={c.node+c.combo}>{c.node} · {c.combo}: {rates(c.equilibrium)} → {rates(c.modeled)}</p>)}</details>
 </section>)}</>}
 </fieldset>;
}
