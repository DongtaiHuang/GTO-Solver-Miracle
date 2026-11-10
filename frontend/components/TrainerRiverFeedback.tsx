"use client";
import {useEffect,useState} from "react";
import type {GameState} from "../lib/types";
import type {StrategyScenarioIndex,StrategyScenario} from "../lib/strategy-types";
import {requestJson} from "../lib/api";
import {RiverResponse} from "./RiverResponse";

function matches(game:GameState,s:StrategyScenario) {
  const hero=game.players[game.hero];
  if(game.actor!==game.hero||hero.position!==s.hero_position||game.pot!==s.pot||
    game.effective_stack!==s.effective_stack||game.big_blind!==s.big_blind||
    game.board.slice(0,3).sort().join()!==s.board.slice(0,3).sort().join()||
    game.board.slice(3).join()!==s.board.slice(3).join())return false;
  const events=game.history.filter(e=>e.seat!==null&&!["small_blind","big_blind"].includes(e.action));
  return events.length===s.history.length && events.every((e,i)=>{
    const h=s.history[i];
    return e.action===h.action && e.street===h.street && game.players[e.seat!].position===h.position &&
      (e.raise_to??(e.action==="call"?e.chips:null))===h.amount;
  });
}
export function TrainerRiverFeedback({game}:{game:GameState}) {
  const [index,setIndex]=useState<StrategyScenarioIndex|null>(null);
  const [error,setError]=useState("");
  const [id,setId]=useState("");
  useEffect(()=>{const c=new AbortController();
    requestJson<StrategyScenarioIndex>("/api/strategy/scenarios",undefined,c.signal)
      .then(v=>{if(!c.signal.aborted)setIndex(v);}).catch(e=>{if(!c.signal.aborted)setError(e.message);});
    return ()=>c.abort();},[]);
  const hero=game.players[game.hero], cards=hero.cards?.slice().sort().join("");
  const combos=hero.position==="BTN"?["AcAd","5c4c"]:["KhQh","KsJs"];
  const combo=combos.find(c=>[c.slice(0,2),c.slice(2)].sort().join("")===cards);
  const entries=index?.scenarios.filter(e=>/^river-(275|550)-(bb|btn)-v1$/.test(e.solution_id)&&matches(game,e.scenario)&&combo)??[];
  const selected=entries.find(e=>e.solution_id===id);
  const opp=game.players.find(p=>p.position===selected?.scenario.opponent_position);
  return <section className="study-card"><h3>Restricted river feedback</h3>
    {error||(!index?"Checking coverage…":!entries.length?"No covered decision for this hand. Opponents use trainer heuristics.":
    <label>Study this decision under the specified ranges and sizing
    <select value={id} onChange={e=>setId(e.target.value)}><option value="">Choose a river tree</option>
    {entries.map(e=><option key={e.solution_id}>{e.solution_id}</option>)}</select></label>)}
    {selected&&opp&&<RiverResponse key={id} scenario={selected.scenario} profile={game.opponents?.[opp.seat-1]?.id??"standard_gto"} heroCombo={combo}/>}
  </section>;
}
