"use client";
import { useEffect, useRef, useState } from "react";
import { requestJson } from "../lib/api";
import type { OpponentProfile, ProfileConfig } from "../lib/study-types";
import type { StrategyResult, StrategyScenarioIndex } from "../lib/strategy-types";
import { StrategyMatrix, FrequencyChart, actionColor, actionLabel } from "./StrategyMatrix";
import { StrategyComparison } from "./StrategyComparison";
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
      if (!controller.signal.aborted) { setRealIndex(real); setExamples(fixtures); }
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
      }
    } catch (err) {
      if (!controller.signal.aborted && currentKey.current === queryKey)
        setError(err instanceof Error ? err.message : "Strategy query failed.");
    } finally { if (!controller.signal.aborted && currentKey.current === queryKey) setBusy(false); }
  }
  return <div className={`strategy-workspace ${demo ? "synthetic-workspace" : ""}`}>
    <section className="study-card solver-scenario" aria-label="Exact strategy scenario">
      <div className="card-heading"><div><p className="eyebrow">EXACT STRATEGY LOOKUP</p><h2>Match the whole situation.</h2></div>
        <span className="data-tag">{demo ? "SYNTHETIC UI EXAMPLES" : "PERMITTED SOLVER DATA"}</span></div>
      <p>Full betting history, stacks, exact board, and sizing abstraction must match.
        Free-form Study notes and equity are never used to guess a solution.</p>
      <label className="demo-switch"><input type="checkbox" checked={demo} onChange={e => changeMode(e.target.checked)} />
        Show synthetic examples (UI only, not GTO)</label>
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
      <p className="coverage-message">{index?.scenarios.length ?? 0} {demo ? "synthetic examples" : "public approved scenarios"} · {index?.message ?? "Loading coverage catalog…"}</p>
      <details className="scenario-json"><summary>Complete scenario configuration (JSON)</summary>
        <label className="field">Exact scenario JSON<textarea rows={16} value={scenarioText}
          onChange={e => { setSelectedScenario(""); setScenarioText(e.target.value); }} spellCheck={false} /></label>
        <p className="field-hint">A strict versioned schema is validated against the poker engine. No fuzzy board, history, position,
          or bet-size substitutions are made. Paste a complete permitted scenario when no supported entry exists.</p></details>
      {error && <div role="alert" className="error-banner">{error}</div>}
      {preview && <div className="strategy-node-summary"><span>{preview.game_format} · {preview.players} players</span>
        <span>{preview.hero_position} vs {preview.opponent_position} · {preview.street}</span>
        <span>Blinds {preview.small_blind}/{preview.big_blind} · ante {preview.ante} · effective {preview.effective_stack} chips · pot {preview.pot}</span>
        <div className="board">{board.map((card,i) => <Card key={i} value={card} />)}</div></div>}
      {visible && <div className={`strategy-status ${visible.status}`} role="status" aria-label="Strategy coverage status">
        <strong>{visible.message}</strong><p>{visible.represented_combos} represented / {visible.unblocked_combos} unblocked combinations.
          Partial coverage never implies a fold recommendation for missing hands.</p>
        <p className="source-id">Scenario {visible.scenario_id}</p></div>}
    </section>

    <div className="strategy-data-grid"><section className="study-card"><div className="card-heading"><h2>{demo ? "Synthetic strategy matrix" : "GTO strategy matrix"}</h2>
      <span className="data-tag">{visible?.status === "available" ? "REVIEWED SOURCE" : demo ? "DEMO ONLY" : "NO VALIDATED MATCH"}</span></div>
      <StrategyMatrix classes={visible?.classes ?? []} actions={visible?.actions ?? []}
        selected={selectedHand} demo={demo} onSelect={hand => { setSelectedHand(hand); setSelectedCombo(""); }} />
      <div className="strategy-action-legend">{visible?.actions.map((action,i) => <span key={action.key}>
        <i style={{ backgroundColor: actionColor(action,i) }} />{actionLabel(action)}</span>)}</div>
      <p className="field-hint">Color segments show action frequencies, not range inclusion. Blank cells mean uncovered combinations.
        {demo ? " All displayed segments are synthetic." : " Only exact, approved and permitted records can fill cells."}</p></section>
      <section className="study-card selected-strategy" aria-label="Selected hand strategy"><div className="card-heading"><h2>{selectedHand} details</h2>
        <span className="data-tag">{demo ? "SYNTHETIC" : visible?.status === "available" ? "SOURCE DATA" : "UNAVAILABLE"}</span></div>
        {selectedClass ? <>
          <p>{selectedClass.represented_combos}/{selectedClass.unblocked_combos} unblocked combinations represented.
            Reach mass {selectedClass.reach_mass.toFixed(3)}.</p>
          <label className="field">Inspect combination<select aria-label="Inspect combination" value={selectedCombo} onChange={e => setSelectedCombo(e.target.value)}>
            <option value="">Class reach-weighted mean</option>{combos.map(c =>
              <option key={c.cards.join("")} value={c.cards.join("")}>{c.cards.join(" ")} · reach {c.reach_weight}</option>)}</select></label>
          <FrequencyChart frequencies={detail?.frequencies ?? selectedClass.frequencies} actions={visible?.actions ?? []}
            label={demo ? "Synthetic selected-hand probabilities" : "Selected-hand action probabilities"} />
          <h3>Action EV</h3>{(detail ? detail.action_ev : selectedClass.action_ev) ? <ul>
            {Object.entries((detail ? detail.action_ev : selectedClass.action_ev)!).map(([action,ev]) =>
              <li key={action}>{action}: {ev.toFixed(3)} chips</li>)}</ul> :
            <p>Validated action EV unavailable. Equity is not substituted for strategy EV.</p>}
        </> : <p>No strategy data for represented, unblocked combinations of this class. GTO solution unavailable.</p>}
        <p className="field-hint">{visible?.aggregation_method ?? "Select an exact scenario and query a source."}</p>
      </section></div>

    <section className="study-card"><div className="card-heading"><h2>Betting history & action abstraction</h2><span className="data-tag">EXACT NODE</span></div>
      {visible ? <div className="history-abstraction"><ol>{visible.scenario.history.length ? visible.scenario.history.map((event,i) =>
        <li key={i}>{i+1}. {event.street}: {event.position} {event.action}{event.amount !== null ? ` ${event.amount}` : ""}</li>) :
        <li>No voluntary actions before this initial decision.</li>}</ol>
        <div><h3>Allowed sizes</h3>{visible.actions.map(action => <p key={action.key}>{actionLabel(action)}</p>)}
          <h3>Abstraction assumptions</h3><ul>{visible.scenario.abstraction.assumptions.map(a => <li key={a}>{a}</li>)}</ul>
          <p className="source-id">{visible.scenario.abstraction.tree_id} · {visible.scenario.abstraction.range_model_id}</p></div></div> :
        <p>Complete engine-validated history and exact action sizes appear after a query.</p>}</section>
    <StrategyComparison result={visible} profiles={profiles} opponent={opponent} onChange={onOpponentChange} />
    <section className="study-card strategy-provenance" aria-label="Solution provenance"><div className="card-heading"><h2>Coverage & provenance</h2><span className="data-tag">{demo ? "SYNTHETIC ONLY" : "SOURCE AUDIT"}</span></div>
      {visible?.source ? <><dl><dt>Solver</dt><dd>{visible.source.solver_identifier} · {visible.source.solver_version}</dd>
        <dt>Source</dt><dd><a href={visible.source.source_url} target="_blank" rel="noreferrer">{visible.source.source_name}</a></dd>
        <dt>License / redistribution</dt><dd><a href={visible.source.license_url} target="_blank" rel="noreferrer">{visible.source.license_name}</a> · {visible.source.redistribution}</dd>
        <dt>Validation</dt><dd>{visible.source.validation_status} · {visible.source.validation_methodology}</dd>
        <dt>Checked / imported</dt><dd>{visible.source.checked_at} / {visible.source.imported_at}</dd></dl>
        <p>{visible.source.mathematical_verification}</p><ul>{visible.source.limitations.map(x => <li key={x}>{x}</li>)}</ul></> :
        <p>No public approved source matched this complete scenario. No confidential catalog entries are disclosed.</p>}
    </section>
  </div>;
}
