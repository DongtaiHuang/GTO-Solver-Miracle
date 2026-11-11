"use client";
import {useEffect,useState} from "react";
import {Card} from "./Card";
import {DecisionReview} from "./DecisionReview";
import {requestJson} from "../lib/api";
import {describe,emptyHand,readHistory,seats} from "../lib/analyzer";
import type {Hand,Pos,Snapshot} from "../lib/analyzer";
import type {Action} from "../lib/types";
const storage="miracle.analyzer.v1.";
const cards=(s:string)=>s.trim().split(/[ ,]+/).filter(Boolean);

export function HandAnalyzer(){
 const [hand,setHand]=useState<Hand>(emptyHand),[states,setStates]=useState<Snapshot[]>([]),[i,go]=useState(0);
 const [error,setError]=useState(""),[busy,setBusy]=useState(false),[size,setSize]=useState("200");
 const [saveName,setName]=useState("My hand"),[saves,setSaves]=useState<string[]>([]),[notice,setNotice]=useState("");
 const [revision,setRevision]=useState(0);
 function install(h:Hand,s:Snapshot[],at:number){setHand(h);setStates(s);go(Math.min(at,s.length-1));setRevision(v=>v+1);}
 function edit(h:Hand){setHand(h);setStates([]);setError("");setNotice("");}
 async function execute(fn:()=>Promise<void>){setBusy(true);setError("");setNotice("");try{await fn();}catch(e){setError(String(e));}finally{setBusy(false);}}
 async function load(raw:string,at=0){const [h,s]=await readHistory(raw);install(h,s,at);}
 useEffect(()=>{let active=true;setBusy(true);
 (async()=>{const from=new URLSearchParams(location.search).get("from")==="trainer";
 const h=from?await requestJson<Hand>("/api/analyzer/trainer"):emptyHand();
 const [validated,steps]=await readHistory(JSON.stringify(h));if(active){install(validated,steps,0);
 setSaves(Object.keys(sessionStorage).filter(k=>k.startsWith(storage)).map(k=>k.slice(storage.length)));}})()
 .catch(e=>{if(active)setError(String(e));}).finally(()=>{if(active)setBusy(false);});return()=>{active=false};},[]);
 const state=states[i],last=i===states.length-1,selected=hand.actions[i];
 function append(action:Action){if(!state?.actor)return; const amount=action==="call"?state.legal.to_call:action==="all_in"?state.legal.max_raise_to:
 action==="bet"||action==="raise"?Number(size):null;
 void execute(()=>load(JSON.stringify({...hand,actions:[...hand.actions,{position:state.actor,street:state.street,action,amount}]}),i+1));}
 return <main className="study-page"><header className="study-header"><div><p className="eyebrow">HAND ANALYZER</p><h1>Hand review workspace</h1></div></header>
 <fieldset disabled={busy} className="analyzer-controls"><details className="study-card"><summary>Enter or edit hand</summary>
 <div className="spot-fields"><label className="field">Hero position<select value={hand.hero} onChange={e=>edit({...hand,hero:e.target.value as Pos})}>{seats.map(p=><option key={p}>{p}</option>)}</select></label>
 {(["small_blind","big_blind","initial_pot"] as const).map(k=><label key={k} className="field">{k.replace("_"," ")}<input type="number" placeholder="Engine derived" value={hand[k]??""} onChange={e=>edit({...hand,[k]:e.target.value===""?null:Number(e.target.value)})}/></label>)}</div>
 {seats.map(p=><div className="analyzer-seat-edit" key={p}><b>{p}</b>{(["name","stack","cards"] as const).map(k=><label key={k} className="field">{p} {k==="cards"&&p!==hand.hero?"showdown cards":k}<input
 value={k==="cards"?(hand.seats[p].cards??[]).join(" "):hand.seats[p][k]} onChange={e=>{const v=e.target.value;
 edit({...hand,seats:{...hand.seats,[p]:{...hand.seats[p],[k]:k==="stack"?Number(v):k==="cards"?(v?v.split(" "):null):v}}});}}/></label>)}</div>)}
 <label className="field">Board in deal order<input value={hand.board.join(" ")} placeholder="Kd 7h 2s Tc 9d" onChange={e=>edit({...hand,board:e.target.value.split(" ")})}/></label>
 <label className="field">Reported payouts (optional, one POS=chips per entry)<input key={revision} defaultValue={Object.entries(hand.payouts??{}).map(([p,n])=>p+"="+n).join(" ")} onBlur={e=>{
 const raw=e.target.value.trim();const payouts=raw?Object.fromEntries(raw.split(/\s+/).map(token=>{const [p,n]=token.split("=");return [p,Number(n)]})):null;
 if(JSON.stringify(payouts)!==JSON.stringify(hand.payouts??null))edit({...hand,payouts});}}/></label>
 <button onClick={()=>void execute(()=>load(JSON.stringify({...hand,board:cards(hand.board.join(" ")),
 seats:Object.fromEntries(seats.map(p=>[p,{...hand.seats[p],cards:hand.seats[p].cards?cards(hand.seats[p].cards!.join(" ")):null}]))}),hand.actions.length))}>Validate hand</button>
 {hand.actions.length>0&&<button onClick={()=>void execute(()=>load(JSON.stringify({...hand,actions:hand.actions.slice(0,-1),payouts:null}),hand.actions.length-1))}>Undo last action</button>}
 <button onClick={()=>void execute(()=>load(JSON.stringify(emptyHand())))}>New history</button></details>
 <details className="study-card"><summary>Save, reopen or transfer JSON</summary><label className="field">Saved hand name<input value={saveName} maxLength={80} onChange={e=>setName(e.target.value)}/></label>
 <button disabled={!states.length||!saveName.trim()} onClick={()=>void execute(async()=>{sessionStorage.setItem(storage+saveName,JSON.stringify(hand));setSaves(Array.from(new Set([...saves,saveName])));setNotice("Saved in this tab.");})}>Save in this tab</button>
 {saves.map(name=><button key={name} onClick={()=>void execute(()=>load(sessionStorage.getItem(storage+name)??""))}>Reopen {name}</button>)}
 <button disabled={!states.length} onClick={()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(hand,null,2)],{type:"application/json"}));
 const a=document.createElement("a");a.href=url;a.download="poker-hand.json";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}}>Export JSON</button>
 <label className="field">Import hand JSON<input type="file" accept=".json" onChange={e=>{const file=e.target.files?.[0];e.target.value="";if(file)void execute(async()=>{if(file.size>1048576)throw Error("History exceeds 1 MiB");await load(await file.text());});}}/></label></details>
 {notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
 {state&&<><section className="study-card"><h2>{state.street} · {state.pot} chips in pot</h2>
 <div className="analyzer-table">{seats.map(p=><div key={p} className={state.actor===p?"acting":""}><b>{p} · {state.players[p].name}</b>
 <p>{state.players[p].stack} chips · bet {state.players[p].bet}</p><small>{state.players[p].status} · contributed {state.players[p].contribution}</small>
 <div className="board">{(state.players[p].cards??[undefined,undefined]).map((c,j)=><Card key={j} value={c} hidden={!c}/>)}</div></div>)}</div>
 <div className="board">{state.board.map(c=><Card key={c} value={c}/>)}</div>
 {state.pending_award&&<p>Showdown unresolved. Enter the missing board or revealed cards to verify payouts.</p>}
 {Object.entries(state.payouts).map(([p,n])=><p key={p}>{p} receives {n} chips</p>)}</section>
 <section className="study-card"><h2>Action timeline</h2><button disabled={!i} onClick={()=>go(i-1)}>Previous decision</button>
 <button disabled={last} onClick={()=>go(i+1)}>Next decision</button>
 {["preflop","flop","turn","river"].map(st=>{const j=states.findIndex(s=>s.street===st);return <button key={st} disabled={j<0} onClick={()=>go(j)}>{st}</button>})}
 <ol>{hand.actions.map((a,j)=><li key={j}><button aria-pressed={i===j} onClick={()=>go(j)}>{j+1}. {a.street} · {describe(a)}</button></li>)}</ol>
 <p>{selected?"Recorded action: "+describe(selected):"End of recorded history"} · Legal alternatives: {state.legal.actions.join(", ")||"none"}</p>
 {last&&state.actor&&(state.board_complete?<><label className="field">Bet or raise to (chips)<input type="number" value={size} onChange={e=>setSize(e.target.value)}/></label>
 <p>Full raise bounds {state.legal.min_raise_to??"—"} to {state.legal.max_raise_to}</p>
 {state.legal.actions.map(a=><button key={a} onClick={()=>append(a)}>Record {a}</button>)}</>:<p>Enter the next street’s board, then validate to continue.</p>)}</section>
 <DecisionReview key={revision+"-"+i} hand={hand} state={state} recorded={selected}/></>}</fieldset></main>;
}
