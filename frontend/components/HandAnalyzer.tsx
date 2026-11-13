"use client";
import {useEffect,useRef,useState} from "react";
import {OpponentIntelligence} from "./OpponentIntelligence";
import {QuickHandSetup} from "./QuickHandSetup";
import {Card} from "./Card";
import {DecisionReview} from "./DecisionReview";
import {requestJson} from "../lib/api";
import {describe,emptyHand,readHistory,seats} from "../lib/analyzer";
import type {Hand,Snapshot} from "../lib/analyzer";
import type {Action} from "../lib/types";
const storage="miracle.analyzer.v1.";
const cards=(s:string)=>s.trim().split(/[ ,]+/).filter(Boolean);

export function HandAnalyzer(){
 const [hand,setHand]=useState<Hand>(emptyHand),[states,setStates]=useState<Snapshot[]>([]),[i,go]=useState(0);
 const [error,setError]=useState(""),[busy,setBusy]=useState(false),[size,setSize]=useState("200");
 const [saveName,setName]=useState("My hand"),[saves,setSaves]=useState<string[]>([]),[notice,setNotice]=useState("");
 const [trainerSource,setTrainerSource]=useState(false);
 const entry=useRef<HTMLDetailsElement>(null);
 const [revision,setRevision]=useState(0);
 function install(h:Hand,s:Snapshot[],at:number){setHand(h);setStates(s);go(Math.min(at,s.length-1));setRevision(v=>v+1);}
 function edit(h:Hand){setHand(h);setStates([]);setError("");setNotice("");}
 async function execute(fn:()=>Promise<void>){setBusy(true);setError("");setNotice("");try{await fn();}catch(e){setError(String(e));}finally{setBusy(false);}}
 async function load(raw:string,at=0){const [h,s]=await readHistory(raw);install(h,s,at);if(entry.current)entry.current.open=false;}
 useEffect(()=>{let active=true;setBusy(true);
 (async()=>{const from=new URLSearchParams(location.search).get("from")==="trainer";
 const saved=new URLSearchParams(location.search).get("saved");
 const h=from?await requestJson<Hand>("/api/analyzer/trainer"):saved?(await requestJson<{hand:Hand}>("/api/account/hands/"+encodeURIComponent(saved))).hand:emptyHand();
 const [validated,steps]=await readHistory(JSON.stringify(h));if(active){setTrainerSource(from);install(validated,steps,0);if(entry.current)entry.current.open=!from;
 setSaves(Object.keys(sessionStorage).filter(k=>k.startsWith(storage)).map(k=>k.slice(storage.length)));}})()
 .catch(e=>{if(active)setError(String(e));}).finally(()=>{if(active)setBusy(false);});return()=>{active=false};},[]);
 const state=states[i],last=i===states.length-1,selected=hand.actions[i];
 function append(action:Action){if(!state?.actor)return; const amount=action==="call"?state.legal.to_call:action==="all_in"?state.legal.max_raise_to:
 action==="bet"||action==="raise"?Number(size):null;
 void execute(()=>load(JSON.stringify({...hand,actions:[...hand.actions,{position:state.actor,street:state.street,action,amount}]}),i+1));}
 return <main className="study-page replay-room"><header className="study-header"><div><p className="eyebrow">HAND ANALYZER</p><h1>Hand review workspace</h1></div></header>
 <fieldset disabled={busy} className="analyzer-controls"><details ref={entry} className="study-card"><summary>Enter or edit hand</summary>
 <QuickHandSetup hand={hand} edit={edit}/>
 <label className="field">Reported payouts (optional, one POS=chips per entry)<input key={revision} defaultValue={Object.entries(hand.payouts??{}).map(([p,n])=>p+"="+n).join(" ")} onBlur={e=>{
 const raw=e.target.value.trim();const payouts=raw?Object.fromEntries(raw.split(/\s+/).map(token=>{const [p,n]=token.split("=");return [p,Number(n)]})):null;
 if(JSON.stringify(payouts)!==JSON.stringify(hand.payouts??null))edit({...hand,payouts});}}/></label>
 <button onClick={()=>void execute(()=>load(JSON.stringify({...hand,board:cards(hand.board.join(" ")),
 seats:Object.fromEntries(seats.map(p=>[p,{...hand.seats[p],cards:hand.seats[p].cards?cards(hand.seats[p].cards!.join(" ")):null}]))}),i))}>Validate hand</button>
 {hand.actions.length>0&&<button onClick={()=>void execute(()=>load(JSON.stringify({...hand,actions:hand.actions.slice(0,-1),payouts:null}),hand.actions.length-1))}>Undo last action</button>}
 <button onClick={()=>void execute(()=>load(JSON.stringify(emptyHand())).then(()=>setTrainerSource(false)))}>New history</button></details>
 <details className="study-card"><summary>Save, reopen or transfer JSON</summary><label className="field">Saved hand name<input value={saveName} maxLength={80} onChange={e=>setName(e.target.value)}/></label>
 <button disabled={!states.length||!saveName.trim()} onClick={()=>void execute(async()=>{sessionStorage.setItem(storage+saveName,JSON.stringify(hand));setSaves(Array.from(new Set([...saves,saveName])));setNotice("Saved in this tab.");})}>Save in this tab</button>
 {saves.map(name=><button key={name} onClick={()=>void execute(()=>load(sessionStorage.getItem(storage+name)??"").then(()=>setTrainerSource(false)))}>Reopen {name}</button>)}
 <button disabled={!states.length} onClick={()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(hand,null,2)],{type:"application/json"}));
 const a=document.createElement("a");a.href=url;a.download="poker-hand.json";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}}>Export JSON</button>
 <label className="field">Import hand JSON<input type="file" accept=".json" onChange={e=>{const file=e.target.files?.[0];e.target.value="";if(file)void execute(async()=>{if(file.size>1048576)throw Error("History exceeds 1 MiB");await load(await file.text());setTrainerSource(false);});}}/></label></details>
 {busy&&<p role="status">Loading validated replay…</p>}{notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
 {state&&<div className="replay-workspace"><section className="study-card reconstructed-hand"><h2>{state.street} · {state.pot} chips in pot</h2>
 <div className="analyzer-table">{seats.map(p=><div key={p} className={state.actor===p?"acting":""}><b>{p}{state.players[p].name!==p && " · "+state.players[p].name}</b>
 <p>{state.players[p].stack} chips · bet {state.players[p].bet}</p><small>{state.players[p].status} · contributed {state.players[p].contribution}</small>
 <div className="board">{(state.players[p].cards??[undefined,undefined]).map((c,j)=><Card key={j} value={c} hidden={!c}/>)}</div></div>)}
 <div className="replay-board" aria-label="Public board"><small>{state.street}</small><div className="board">
 {Array.from({length:5},(_,index)=><Card key={index} value={state.board[index]}/>)}</div></div></div>
 {state.pending_award&&<p>Showdown unresolved. Enter the missing board or revealed cards to verify payouts.</p>}
 {Object.entries(state.payouts).map(([p,n])=><p key={p}>{p} receives {n} chips</p>)}</section>
 <section className="study-card replay-timeline"><h2>Action timeline</h2><button disabled={!i} onClick={()=>go(i-1)}>Previous decision</button>
 <button disabled={last} onClick={()=>go(i+1)}>Next decision</button>
 {["preflop","flop","turn","river"].map(st=>{const j=states.findIndex(s=>s.street===st);return <button key={st} disabled={j<0} onClick={()=>go(j)}>{st}</button>})}
 <ol>{hand.actions.map((a,j)=><li key={j}><button aria-pressed={i===j} onClick={()=>go(j)}>{j+1}. {a.street} · {describe(a)}</button></li>)}</ol>
 <p>{selected?"Recorded action: "+describe(selected):"End of recorded history"} · Legal alternatives: {state.legal.actions.join(", ")||"none"}</p>
 {last&&state.actor&&(state.board_complete?<><label className="field">Bet or raise to (chips)<input type="number" value={size} onChange={e=>setSize(e.target.value)}/></label>
 <p>Full raise bounds {state.legal.min_raise_to??"—"} to {state.legal.max_raise_to}</p>
 {state.legal.actions.map(a=><button key={a} onClick={()=>append(a)}>Record {a}</button>)}</>:<button onClick={()=>{if(entry.current){entry.current.open=true;entry.current.scrollIntoView();entry.current.querySelector<HTMLInputElement>('input[placeholder="Flop · turn · river"]')?.focus();}}}>Enter {state.street} board</button>)}</section>
 <DecisionReview key={revision+"-"+i} hand={hand} state={state} recorded={selected}/></div>}</fieldset><OpponentIntelligence hand={states.length&&!trainerSource&&!hand.trainer_hand_id?hand:undefined}/></main>;
}
