"use client";
import {useEffect,useState} from "react";
import {seats,type Hand,type Pos} from "../lib/analyzer";
import {requestJson} from "../lib/api";
import {captureError,changed,emptyArchive,persist,readArchive,scrub,type Archive,type Archetype,type Report} from "../lib/observations";

const labels:Record<string,string>={vpip:"VPIP",pfr:"PFR",three_bet:"3-bet",fold_to_three_bet:"Fold to 3-bet",flop_cbet:"Flop c-bet",
 fold_to_flop_cbet:"Fold to flop c-bet",turn_aggression:"Turn aggression",river_aggression:"River aggression",postflop_call:"Call facing bet",postflop_fold:"Fold facing bet"};
const pct=(v:number|null)=>v===null?"—":(100*v).toFixed(1)+"%";
const archetypes=["tag","lag","tp","lp"] as const;

export function OpponentIntelligence({hand,onAdopt}:{hand?:Hand;onAdopt?:(seat:number,id:Archetype)=>void}){
 const [open,setOpen]=useState(false),[tick,setTick]=useState(0),[reports,setReports]=useState<Report[]>([]);
 const [selected,setSelected]=useState(""),[error,setError]=useState(""),[message,setMessage]=useState(""),[busy,setBusy]=useState(false);
 const [handId,setHandId]=useState(""),[mapping,setMapping]=useState<Partial<Record<Pos,string>>>({});
 const player=reports.find(r=>r.id===selected)??reports[0];
 useEffect(()=>{const refresh=()=>setTick(i=>i+1);window.addEventListener(changed,refresh);return()=>window.removeEventListener(changed,refresh);},[]);
 useEffect(()=>{
   if(!open)return;
   const c=new AbortController();
   (async()=>{const archive=readArchive();const result=await requestJson<Report[]>("/api/observations/report",{archive},c.signal);
    if(!c.signal.aborted){setReports(result);setError("");}})().catch(e=>{if(!c.signal.aborted){setReports([]);setError(String(e));}});
   return()=>c.abort();
 },[open,tick]);
 async function commit(build:(a:Archive)=>Archive,note:string){
   setError("");setMessage("");setBusy(true);
   try{const current=readArchive(),next=build(current);
    const result=await requestJson<Report[]>("/api/observations/report",{archive:next});
    if(JSON.stringify(readArchive())!==JSON.stringify(current))throw Error("Archive changed; retry the operation.");
    persist(next);setReports(result);setMessage(note);return result;
   }catch(e){setError(String(e));}finally{setBusy(false);}
 }
 function add(){
   if(!hand)return;
   const ids=Object.fromEntries(Object.entries(mapping).filter(([,v])=>v).map(([pos,v])=>[pos,v==="new"?"player-"+crypto.randomUUID():v]));
   if(!Object.keys(ids).length||!handId.trim()){setError("Enter a stable hand reference and map at least one seat.");return;}
   void commit(a=>({...a,entries:[...a.entries,{hand_id:handId.trim(),source:"manual",mapping:ids,hand:scrub(hand)}]}), "Hand recorded.").then(result=>{
     if(!result)return;
     const contributors=result.filter(r=>Object.values(ids).includes(r.id));
     setSelected(contributors[0].id);
     setMessage(contributors.map(r=>{
       const counts=r.history.find(h=>h.hand_id===handId.trim())!.counts;
       return r.name+" · "+(Object.entries(counts).map(([k,[s,n]])=>labels[k]+" "+s+"/"+n).join(", ")||"No resolved opportunities");
     }).join(" | "));
   });
 }
 async function importFile(file:File){
   try{
     if(file.size>1000000)throw Error("Archive exceeds 1 MB");
     const raw=await file.text();
     // Send original bytes for duplicate-key validation before parsing locally.
     const verified=await fetch("/api/observations/report",{method:"POST",headers:{"Content-Type":"application/json"},body:'{"archive":'+raw+'}'});
     if(!verified.ok)throw Error("Invalid observation archive: "+await verified.text());
     const imported:Archive=JSON.parse(raw);
     if(window.confirm("Replace this tab’s observation archive with the validated file?"))await commit(()=>imported,"Archive restored.");
   }catch(e){setError(String(e));}
 }
 function download(){
   try{const blob=new Blob([JSON.stringify(readArchive(),null,2)],{type:"application/json"});const url=URL.createObjectURL(blob);
    const a=document.createElement("a");a.href=url;a.download="opponent-observations-v1.json";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
   }catch(e){setError(String(e));}
 }
 return <details className="study-card observation-panel" onToggle={e=>setOpen(e.currentTarget.open)}>
 <summary>Opponent observations</summary>
 {captureError&&<p role="alert">{captureError}</p>}
 {open&&<fieldset disabled={busy}><legend>Tab-local action history</legend>
 {error&&<p role="alert">{error}</p>}{message&&<p role="status">{message}</p>}
 {hand&&<details><summary>Add this hand to opponent observations</summary>
 <p>Map recorded seats explicitly. Choosing New creates a separate identity even when names match.</p>
 <label className="field">Hand reference<input value={handId} maxLength={80} placeholder="Unique letters, digits, hyphens or underscores" onChange={e=>setHandId(e.target.value)}/></label>
 <div className="quick-fields">{seats.map(pos=><label className="field" key={pos}>{pos} · {hand.seats[pos].name}<select aria-label={"Map "+pos} value={mapping[pos]??""} onChange={e=>setMapping({...mapping,[pos]:e.target.value})}>
 <option value="">Skip player</option><option value="new">New manual identity</option>{reports.filter(r=>r.source==="manual").map(r=><option key={r.id} value={r.id}>{r.name} · {r.id.slice(-8)}</option>)}</select></label>)}</div>
 <button onClick={add}>Record mapped players</button></details>}
 {player?<><label className="field">Observed player<select value={player.id} onChange={e=>setSelected(e.target.value)}>
 {reports.map(r=><option key={r.id} value={r.id}>{r.name} · {r.source} · {r.id.slice(-8)}</option>)}</select></label>
 <h3>{player.name} · {player.hands} observed hands</h3><p>{player.source==="trainer"?"Heuristic Trainer actions":"Manually recorded actions"} · Provisional classification: {player.provisional?.toUpperCase()??"Unknown / Insufficient Data"}</p>
 <p>{player.evidence}</p>
 <label className="field">Manual label override<select aria-label="Manual label override" value={player.override??""} onChange={e=>{
 const value=e.target.value as Archetype|"";void commit(a=>{const overrides={...a.overrides};if(value)overrides[player.id]=value;else delete overrides[player.id];return {...a,overrides};},"Label updated.");}}>
 <option value="">Use inferred label</option>{archetypes.map(v=><option key={v} value={v}>{v.toUpperCase()}</option>)}</select></label>
 {onAdopt&&/^bot-[1-5]$/.test(player.id)&&player.source==="trainer"&&player.provisional&&
 <button onClick={()=>{onAdopt(Number(player.id.slice(4)),player.provisional!);setMessage("Preset selected for the next hand.");}}>Use inferred {player.provisional.toUpperCase()} preset next hand</button>}
 <div className="stat-scroll"><table className="hand-actions"><caption>Observed actions and Beta(1,1) posterior estimates</caption>
 <thead><tr>{["Metric","Count","Observed","Estimate","95% interval","Evidence"].map(t=><th key={t}>{t}</th>)}</tr></thead><tbody>
 {Object.entries(player.metrics).map(([k,m])=><tr key={k}><th>{labels[k]}</th><td>{m.successes}/{m.opportunities}</td><td>{pct(m.observed)}
 {m.observed!==null&&<span className="action-meter"><i style={{width:pct(m.observed),background:"#86b994"}}/></span>}</td><td>{pct(m.estimate)}</td>
 <td>{m.interval?m.interval.map(pct).join(" – "):"—"}</td><td>{!m.opportunities?"Insufficient data":m.sufficient?"20+ trials":"Small sample"}</td></tr>)}</tbody></table></div>
 <details><summary>Recorded evidence</summary>{player.history.slice().reverse().map(h=><p key={h.hand_id}><b>{h.hand_id} · {h.position} · {h.stack} chips</b><br/>{h.actions.join(" → ")||"No recorded action"}<br/>
 {Object.entries(h.counts).map(([k,[s,n]])=>labels[k]+" "+s+"/"+n).join(" · ")}</p>)}</details>
 <button onClick={()=>{if(window.confirm("Delete this player’s observations?"))void commit(a=>{
 const entries=a.entries.map(e=>({...e,mapping:Object.fromEntries(Object.entries(e.mapping).filter(([,id])=>id!==player.id))})).filter(e=>Object.keys(e.mapping).length);
 const overrides={...a.overrides};delete overrides[player.id];return {...a,entries,overrides};},"Player removed.");}}>Delete player observations</button></>:<p>No observed players in this tab.</p>}
 <details><summary>Manage observation archive</summary><button onClick={download}>Export observations</button>
 <label className="field">Import observations<input type="file" accept=".json" onChange={e=>{const file=e.target.files?.[0];e.target.value="";if(file)void importFile(file);}}/></label>
 <button onClick={()=>{if(window.confirm("Reset all opponent observations in this tab?")){persist(emptyArchive());setMessage("Archive reset.");}}}>Reset observations</button></details>
 <p>These estimates describe recorded opportunities. Solver baselines and combo-specific river models use their own inputs.</p>
 </fieldset>}</details>;
}
