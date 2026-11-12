import type {Hand,Pos} from "./analyzer";
export type Archetype="tag"|"lag"|"tp"|"lp";
export interface Entry {hand_id:string;source:"manual"|"trainer";mapping:Partial<Record<Pos,string>>;hand:Hand}
export interface Archive {version:"1.0";entries:Entry[];overrides:Record<string,Archetype>}
export interface Stat {successes:number;opportunities:number;observed:number|null;estimate:number|null;interval:[number,number]|null;sufficient:boolean}
export interface Report {id:string;name:string;source:Entry["source"];hands:number;metrics:Record<string,Stat>;provisional:Archetype|null;override:Archetype|null;evidence:string;
 history:{hand_id:string;position:Pos;stack:number;actions:string[];counts:Record<string,[number,number]>}[]}
const key="miracle.observations.v1";
export const changed="miracle-observations-updated";
export let captureError="";
export function emptyArchive():Archive{return {version:"1.0",entries:[],overrides:{}};}
export function readArchive():Archive{return JSON.parse(sessionStorage.getItem(key)??JSON.stringify(emptyArchive()));}
export function persist(next:Archive){
  const raw=JSON.stringify(next);
  if(new Blob([raw]).size>1000000||next.entries.length>128||next.entries.reduce((n,e)=>n+e.hand.actions.length,0)>4096)
    throw Error("Observation capacity reached. Export and reset the archive.");
  sessionStorage.setItem(key,raw);
  captureError="";
  window.dispatchEvent(new Event(changed));
}
export function captureCompleted(entry:Entry){
  try {
    const archive=readArchive();
    if(sessionStorage.getItem(key+".lastTrainer")===entry.hand_id||archive.entries.some(e=>e.hand_id===entry.hand_id))return;
    persist({...archive,entries:[...archive.entries,entry]});
    sessionStorage.setItem(key+".lastTrainer",entry.hand_id);
  }catch(e){captureError=String(e);window.dispatchEvent(new Event(changed));}
}
export function scrub(hand:Hand):Hand{return {...hand,payouts:null,seats:Object.fromEntries(Object.entries(hand.seats).map(([pos,seat])=>[pos,{...seat,cards:null}])) as Hand["seats"]};}
