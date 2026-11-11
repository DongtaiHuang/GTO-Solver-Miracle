import type {Action,Street,LegalActions} from "./types";
export const seats=["BTN","SB","BB","UTG","HJ","CO"] as const;
export type Pos=typeof seats[number];
export interface Event {position:Pos;street:Street;action:Action;amount:number|null}
export interface Hand {version:"1.0";hero:Pos;small_blind:number;big_blind:number; initial_pot?:number|null;
 seats:Record<Pos,{name:string;stack:number;cards:string[]|null}>;board:string[];actions:Event[];payouts?:Partial<Record<Pos,number>>|null}
export interface Snapshot {street:Street;actor:Pos|null;board:string[];board_complete:boolean;pot:number;
 players:Record<Pos,{name:string;stack:number;bet:number;contribution:number;cards:string[]|null;status:string}>;
 legal:LegalActions;texture:{paired:boolean|null;max_suit_count:number;rank_span:number|null};odds:number|null;
 payouts:Partial<Record<Pos,number>>;pending_award:boolean;candidates:string[]}
export function emptyHand():Hand {
 return {version:"1.0",hero:"BTN",small_blind:50,big_blind:100,board:[],actions:[],
 seats:Object.fromEntries(seats.map(p=>[p,{name:p,stack:10000,cards:null}])) as Hand["seats"]};
}
export function describe(e:Event){return e.position+" "+e.action+(e.amount===null?"":" "+e.amount);}
export async function readHistory(raw:string):Promise<[Hand,Snapshot[]]> {
 if(raw.length>1024*1024)throw new Error("History exceeds 1 MiB");
 const res=await fetch("/api/analyzer/replay",{method:"POST",headers:{"Content-Type":"application/json"},body:raw,cache:"no-store"});
 const data=await res.json();
 if(!res.ok)throw new Error(typeof data.detail==="string"?data.detail:JSON.stringify(data.detail));
 return [JSON.parse(raw),data];
}
