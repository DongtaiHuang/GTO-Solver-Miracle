import {useState} from "react";
import {seats,type Hand,type Pos} from "../lib/analyzer";

export function QuickHandSetup({hand,edit}:{hand:Hand;edit:(hand:Hand)=>void}) {
  const [opponent,setOpponent]=useState<Pos>("BB");
  const others=seats.filter(p=>p!==hand.hero);
  const other=opponent===hand.hero?others[0]:opponent;
  const stacks=seats.map(p=>hand.seats[p].stack);
  function updateSeat(p:Pos,changes:Partial<Hand["seats"][Pos]>) {
    edit({...hand,seats:{...hand.seats,[p]:{...hand.seats[p],...changes}}});
  }
  function cardInput(p:Pos,label:string) {
    return <label className="field">{label}<input placeholder="Unknown" value={hand.seats[p].cards?.join(" ")??""}
      onChange={e=>updateSeat(p,{cards:e.target.value?e.target.value.split(" "):null})}/></label>;
  }
  return <>
    <div className="quick-fields">
      <label className="field">Hero position<select value={hand.hero} onChange={e=>edit({...hand,hero:e.target.value as Pos})}>
        {seats.map(p=><option key={p}>{p}</option>)}</select></label>
      {cardInput(hand.hero,hand.hero+" cards")}
      <label className="field">All six starting stacks (chips)<input type="number" min="1" placeholder="Mixed stacks"
        value={stacks.every(v=>v===stacks[0])?stacks[0]:""} onChange={e=>edit({...hand,seats:Object.fromEntries(
          seats.map(p=>[p,{...hand.seats[p],stack:Number(e.target.value)}])) as Hand["seats"]})}/></label>
      {(["small_blind","big_blind"] as const).map(k=><label className="field" key={k}>{k.replace("_"," ")}
        <input type="number" min="1" value={hand[k]} onChange={e=>edit({...hand,[k]:Number(e.target.value)})}/></label>)}
      <label className="field">Opponent to edit<select value={other} onChange={e=>setOpponent(e.target.value as Pos)}>
        {others.map(p=><option key={p}>{p}</option>)}</select></label>
      {cardInput(other,other+" revealed cards (optional)")}
      <label className="field">Board in deal order<input placeholder="Flop · turn · river" value={hand.board.join(" ")}
        onChange={e=>edit({...hand,board:e.target.value.split(" ")})}/></label>
    </div>
    <details className="advanced-setup"><summary>Advanced setup · six seats</summary>
      {seats.map(p=><div className="analyzer-seat-edit" key={p}><b>{p}</b>
        <label className="field">{p} name<input value={hand.seats[p].name} onChange={e=>updateSeat(p,{name:e.target.value})}/></label>
        <label className="field">{p} stack<input type="number" value={hand.seats[p].stack} onChange={e=>updateSeat(p,{stack:Number(e.target.value)})}/></label>
        {cardInput(p,p+" known cards")}</div>)}
      <label className="field">Initial pot (optional check)<input type="number" placeholder="Engine derived" value={hand.initial_pot??""}
        onChange={e=>edit({...hand,initial_pot:e.target.value===""?null:Number(e.target.value)})}/></label>
    </details>
  </>;
}
