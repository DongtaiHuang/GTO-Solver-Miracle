"use client";
import { useEffect, useRef, useState } from "react";
import { requestJson } from "../lib/api";
import type { OpponentProfile, ProfileConfig } from "../lib/study-types";
import type { StrategyResult, StrategyScenarioIndex } from "../lib/strategy-types";
import { StrategyMatrix, actionColor, actionLabel } from "./StrategyMatrix";
import { StrategyComparison } from "./StrategyComparison";
import {MultiResponse} from "./MultiResponse";
import { RiverResponse } from "./RiverResponse";
import { HandActions } from "./HandActions";
import { Card } from "./Card";

export function StrategyWorkspace({ profiles, opponent, onOpponentChange }: {
  profiles: OpponentProfile[]; opponent: ProfileConfig; onOpponentChange: (value: ProfileConfig) => void;
}) {
  const [realIndex, setRealIndex] = useState<StrategyScenarioIndex | null>(null);
  const [examples, setExamples] = useState<StrategyScenarioIndex | null>(null);
  const [demo, setDemo] = useState(false);
  const [scenarioText, setScenarioText] = useState("{}");
  const [selectedScenario, setSelectedScenario] = useState("");
  const [selectedHand, setSelectedHand] = useState("AA");
  const [selectedCombo, setSelectedCombo] = useState("");
  const [result, setResult] = useState<StrategyResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [catalogError, setCatalogError] = useState("");
  const requestRef = useRef<AbortController | null>(null);
  const key = JSON.stringify([demo,scenarioText]);
  const currentKey = useRef(key); currentKey.current = key;
  const resultKey = useRef("");
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      requestJson<StrategyScenarioIndex>("/api/strategy/scenarios", undefined, controller.signal),
      requestJson<StrategyScenarioIndex>("/api/strategy/examples", undefined, controller.signal),
    ]).then(([real, fixtures]) => {
      if (controller.signal.aborted) return;
      setRealIndex(real); setExamples(fixtures);
      const params=new URLSearchParams(window.location.search);
      if (params.has("source") || params.has("scenario")) {
        const record=real.scenarios.find(s=>s.solution_id===params.get("source") && s.scenario_id===params.get("scenario"));
        if(record){setSelectedScenario(record.solution_id);setScenarioText(JSON.stringify(record.scenario,null,2));}
        else setCatalogError("This decision has no exact published strategy.");
      }
    }).catch(err => { if (!controller.signal.aborted) setCatalogError(err instanceof Error ? err.message : "Strategy catalog unavailable."); });
    return () => { controller.abort(); requestRef.current?.abort(); };
  }, []);
  useEffect(() => {
    requestRef.current?.abort(); setResult(null); setBusy(false); setError(""); setSelectedCombo("");
  }, [key]);
  const index = demo ? examples : realIndex;
  const visible = result && resultKey.current === key ? result : null;
  const selectedClass = visible?.classes.find(c => c.hand_class === selectedHand);
  const combos = visible?.combinations.filter(c => c.hand_class === selectedHand) ?? [];
  const detail = combos.find(c => c.cards.join("") === selectedCombo);
  const preview = visible?.scenario ?? index?.scenarios.find(s => s.solution_id === selectedScenario)?.scenario;
  const board = preview?.board ?? [];
  function changeMode(next: boolean) {
    setDemo(next); setSelectedScenario(""); setScenarioText("{}");
  }
  async function query() {
    requestRef.current?.abort();
    const controller = new AbortController(); requestRef.current = controller;
    const queryKey = key;
    setError(""); setBusy(true); setResult(null);
    try {
      const scenario: unknown = JSON.parse(scenarioText);
      const data = await requestJson<StrategyResult>("/api/strategy/query",
        { scenario, mode: demo ? "synthetic_demo" : "validated_gto" }, controller.signal);
      if (!controller.signal.aborted && currentKey.current === queryKey) {
        resultKey.current = queryKey; setResult(data);
        setSelectedHand(hand => data.classes.some(c=>c.hand_class===hand) ? hand : data.classes[0]?.hand_class ?? hand);
      }
    } catch (err) {
      if (!controller.signal.aborted && currentKey.current === queryKey)
        setError(err instanceof Error ? err.message : "Strategy query failed.");
    } finally { if (!controller.signal.aborted && currentKey.current === queryKey) setBusy(false); }
  }
  return <div className={`strategy-workspace ${demo ? "synthetic-workspace" : ""}`}>
    <section className="study-card solver-scenario" aria-label="Exact strategy scenario">
      {demo && <div className="demo-notice" role="note"><b>SYNTHETIC DEMONSTRATION — NOT GTO</b>
        <p>All example probabilities are fabricated to demonstrate the interface, not recommendations.
          Synthetic examples cannot be promoted to validated baselines or supply action EV.</p></div>}
      {catalogError && <div role="alert" className="error-banner">{catalogError}</div>}
      <div className="scenario-query-row"><label className="field">Supported exact scenario
        <select aria-label="Supported exact scenario" value={selectedScenario} onChange={e => {
          const record = index?.scenarios.find(s => s.solution_id === e.target.value);
          setSelectedScenario(e.target.value); setScenarioText(record ? JSON.stringify(record.scenario,null,2) : "{}");
        }}><option value="">{index?.scenarios.length ? "Select a complete scenario…" :
          demo ? "Loading synthetic examples…" : "No validated scenarios available"}</option>
          {index?.scenarios.map(s => <option key={s.solution_id} value={s.solution_id}>{s.label}</option>)}
        </select></label><button className="primary" onClick={() => void query()} disabled={busy}>
          {busy ? "Looking up strategy…" : "Query exact strategy"}</button></div>
      <div className="lookup-options">      <label className="demo-switch"><input type="checkbox" checked={demo} onChange={e => changeMode(e.target.checked)} />
        Show synthetic examples (UI only, not GTO)</label>
<small className="coverage-message">{index ? index.scenarios.length+" "+(demo?"synthetic examples":"public approved scenarios") : "Loading scenarios…"}</small></div>

      {error && <div role="alert" className="error-banner">{error}</div>}
      {preview && <div className="strategy-node-summary">
        <div className="node-position"><small>{preview.game_format}</small><b>{preview.hero_position} vs {preview.opponent_position}</b></div>
        <div className="node-board"><small>{preview.street}</small><div className="board">{board.map(card => <Card key={card} value={card}/>)}</div></div>
        <div><small>Pot</small><b>{preview.pot} chips</b></div>
        <div title="Smaller remaining stack between these players"><small>Effective stack</small><b>{preview.effective_stack} chips</b></div>
        <div><small>Blinds / ante</small><b>{preview.small_blind}/{preview.big_blind} · {preview.ante}</b></div>
      </div>}
      {preview?.abstraction.tree_id==="turn-river-halfpot-v1" && <p className="field-hint">Joint turn–river solve · Turn EV includes future betting on every legal river. Published river continuations: 9♦ and A♠.</p>}
      {visible && <div className={`strategy-status ${visible.status}`} role="status" aria-label="Strategy coverage status">
        <strong>{visible.status==="available"?"Exact solver match":visible.message}</strong><span>{visible.represented_combos} represented / {visible.unblocked_combos} unblocked combos</span>
</div>}
    </section>

    <div className="strategy-data-grid"><section className="study-card"><div className="card-heading"><h2>{demo ? "Synthetic strategy matrix" : "GTO strategy matrix"}</h2>
      <span className="data-tag">{visible?.status === "available" ? "REVIEWED SOURCE" : demo ? "DEMO ONLY" : "NO VALIDATED MATCH"}</span></div>
      <StrategyMatrix classes={visible?.classes ?? []} actions={visible?.actions ?? []}
        selected={selectedHand} demo={demo} onSelect={hand => { setSelectedHand(hand); setSelectedCombo(""); }} />
      <div className="strategy-action-legend">{visible?.actions.map((action) => <span key={action.key}>
        <i style={{ backgroundColor: actionColor(action,visible.actions) }} />{actionLabel(action)}</span>)}</div>
      <p className="field-hint">Striped cells have no coverage. Use arrow keys to inspect neighboring hands.</p></section>
      <section className="study-card selected-strategy" aria-label="Selected hand strategy"><div className="card-heading"><h2>{selectedHand} details</h2>
        <span className="data-tag">{demo ? "SYNTHETIC" : visible?.status === "available" ? "SOURCE DATA" : "UNAVAILABLE"}</span></div>
        {selectedClass ? <>
          <p>{selectedClass.represented_combos}/{selectedClass.unblocked_combos} unblocked combinations represented.
            Reach mass {selectedClass.reach_mass.toFixed(3)}.</p>
          <label className="field">Inspect combination<select aria-label="Inspect combination" value={selectedCombo} onChange={e => setSelectedCombo(e.target.value)}>
            <option value="">Class reach-weighted mean</option>{combos.map(c =>
              <option key={c.cards.join("")} value={c.cards.join("")}>{c.cards.join(" ")} · reach {c.reach_weight}</option>)}</select></label>
          <HandActions actions={visible?.actions??[]} frequencies={detail?.frequencies??selectedClass.frequencies}
            ev={detail?detail.action_ev:selectedClass.action_ev}/>
          {!(detail?detail.action_ev:selectedClass.action_ev) && <p>Validated action EV unavailable.</p>}
        </> : <p>{visible ? "No strategy data for this class in the selected scenario." : "Select a scenario and query its strategy to inspect this hand."}</p>}
        <p className="field-hint" title="A combination is one exact pair of hole cards. Reach is its relative weight at this decision.">Class averages weight each covered combo by its reach.</p>
        {visible?.status==="available" && visible.source && detail && <a className="button-link" href={"/training?source="+visible.source.solution_id+"&scenario="+visible.scenario_id+"&combo="+detail.cards.join("")}>Practice this combination</a>}
        <a className="compare-link" href="#study-comparison">Compare opponent strategies ↓</a>
      </section></div>

    <section id="study-comparison" className="comparison-workspace" tabIndex={-1}><div className="comparison-toolbar"><h2>Opponent comparison</h2>
      <label>Archetype <select aria-label="Comparison archetype" value={opponent.id} onChange={e=>{const next=profiles.find(p=>p.id===e.target.value);if(next)onOpponentChange({id:next.id,parameters:next.parameters});}}>{profiles.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label></div>
    <StrategyComparison result={visible} profiles={profiles} opponent={opponent} onChange={onOpponentChange} />
    {visible?.status==="available" && visible.source?.solution_id.startsWith("ts-") &&
      <MultiResponse key={visible.scenario_id+opponent.id} strategy={visible} profile={opponent.id} selection={{hand:selectedHand,select:hand=>{setSelectedHand(hand);setSelectedCombo("");}}}
        combos={detail?[detail.cards.join("")]:combos.map(c=>c.cards.join(""))}/>}
    {visible?.status==="available" && /^river-(275|550)-(btn|bb)-v1$/.test(visible.source?.solution_id??"") &&
      <RiverResponse study heroCombo={detail?.cards.join("")} key={visible.scenario_id+opponent.id} scenario={visible.scenario} profile={opponent.id}/>}
    </section>
    <details className="study-card research-panel"><summary>Betting history &amp; action abstraction</summary>
      {visible ? <div className="history-abstraction"><ol>{visible.scenario.history.length ? visible.scenario.history.map((event,i) =>
        <li key={i}>{i+1}. {event.street}: {event.position} {event.action}{event.amount !== null ? ` ${event.amount}` : ""}</li>) :
        <li>No voluntary actions before this initial decision.</li>}</ol>
        <div><h3>Allowed sizes</h3>{visible.actions.map(action => <p key={action.key}>{actionLabel(action)}</p>)}
          <h3>Abstraction assumptions</h3><ul>{visible.scenario.abstraction.assumptions.map(a => <li key={a}>{a}</li>)}</ul>
          <p className="source-id">{visible.scenario.abstraction.tree_id} · {visible.scenario.abstraction.range_model_id}</p></div></div> :
        <p>Complete engine-validated history and exact action sizes appear after a query.</p>}</details>
      <details className="scenario-json"><summary>Complete scenario configuration (JSON)</summary>
        <label className="field">Exact scenario JSON<textarea rows={16} value={scenarioText}
          onChange={e => { setSelectedScenario(""); setScenarioText(e.target.value); }} spellCheck={false} /></label>
        <p className="field-hint">A strict versioned schema is validated against the poker engine. No fuzzy board, history, position,
          or bet-size substitutions are made. Paste a complete permitted scenario when no supported entry exists.</p></details>
    <section className="study-card strategy-provenance" aria-label="Solution provenance">
    <details><summary>Coverage &amp; provenance</summary>
      {visible && <p className="source-id">Scenario {visible.scenario_id}</p>}
      {visible?.source ? <><dl><dt>Solver</dt><dd>{visible.source.solver_identifier} · {visible.source.solver_version}</dd>
        <dt>Source</dt><dd><a href={visible.source.source_url} target="_blank" rel="noreferrer">{visible.source.source_name}</a></dd>
        <dt>License / redistribution</dt><dd><a href={visible.source.license_url} target="_blank" rel="noreferrer">{visible.source.license_name}</a> · {visible.source.redistribution}</dd>
        <dt>Validation</dt><dd>{visible.source.validation_status} · {visible.source.validation_methodology}</dd>
        <dt>Checked / imported</dt><dd>{visible.source.checked_at} / {visible.source.imported_at}</dd></dl>
        <p>{visible.source.mathematical_verification}</p><ul>{visible.source.limitations.map(x => <li key={x}>{x}</li>)}</ul></> :
        <p>No public approved source matched this complete scenario. No confidential catalog entries are disclosed.</p>}
    </details></section>
  </div>;
}
