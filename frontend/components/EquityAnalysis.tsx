"use client";
import { useEffect, useRef, useState } from "react";
import { requestJson } from "../lib/api";
import type { EquityMethod, EquityResult, PotOddsResult } from "../lib/equity-types";
import type { StudyRequest, StudyResult } from "../lib/study-types";

const cards = (text: string) => text.trim().split(/[\s,]+/).filter(Boolean).map(
  card => card[0].toUpperCase() + card.slice(1).toLowerCase());
const percent = (value: number) => `${(100 * value).toFixed(2)}%`;
const message = (error: unknown) => error instanceof Error ? error.message : "Calculation failed. Please check the inputs.";

export function EquityAnalysis({ request, study, onAdoptRange }: {
  request: StudyRequest; study: StudyResult | null; onAdoptRange: (weights: Record<string, number>) => void;
}) {
  const [heroMode, setHeroMode] = useState<"hand" | "range">("hand");
  const [opponentMode, setOpponentMode] = useState<"range" | "hand">("range");
  const [opponentCards, setOpponentCards] = useState("");
  const [dead, setDead] = useState("");
  const [method, setMethod] = useState<EquityMethod>("auto");
  const [samples, setSamples] = useState("2000");
  const [seed, setSeed] = useState("42");
  const [result, setResult] = useState<EquityResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [call, setCall] = useState("0");
  const [odds, setOdds] = useState<PotOddsResult | null>(null);
  const [oddsBusy, setOddsBusy] = useState(false);
  const [oddsError, setOddsError] = useState("");
  const revision = useRef(0);
  const computation = useRef<AbortController | null>(null);
  const oddsComputation = useRef<AbortController | null>(null);
  const resultKey = useRef("");
  const oddsKey = useRef("");
  const inputKey = JSON.stringify({ board: request.spot.board, heroMode, opponentMode,
    hero: heroMode === "hand" ? request.spot.hero_cards : request.hero_range,
    opponent: opponentMode === "hand" ? opponentCards : request.opponent_range,
    dead, method, samples, seed });
  const currentKey = useRef(inputKey);
  currentKey.current = inputKey;
  const currentOddsKey = useRef("");
  currentOddsKey.current = JSON.stringify([inputKey, request.spot.pot, call]);
  useEffect(() => {
    revision.current++; computation.current?.abort(); oddsComputation.current?.abort();
    setResult(null); setOdds(null); setError(""); setOddsError(""); setBusy(false); setOddsBusy(false);
    return () => { computation.current?.abort(); oddsComputation.current?.abort(); };
  }, [inputKey]);
  useEffect(() => { oddsComputation.current?.abort(); setOdds(null); setOddsError(""); setOddsBusy(false); }, [call, request.spot.pot]);

  const needsAssumption = opponentMode === "range" && request.opponent_range === null;
  const heroReady = heroMode === "hand" ? request.spot.hero_cards.length === 2 :
    Object.values(request.hero_range.weights).some(weight => weight > 0);
  const opponentReady = opponentMode === "hand" ? cards(opponentCards).length === 2 :
    !needsAssumption && Object.values(request.opponent_range?.weights ?? {}).some(weight => weight > 0);
  const integer = (value: string, low: number, high: number) => value.trim() !== "" &&
    Number.isSafeInteger(Number(value)) && Number(value) >= low && Number(value) <= high;
  const canCalculate = heroReady && opponentReady && integer(samples, 100, 10000) && integer(seed, 0, 4294967295);
  const visibleResult = result && resultKey.current === inputKey ? result : null;
  const visibleOdds = odds && oddsKey.current === currentOddsKey.current ? odds : null;
  const hero = visibleResult?.players[0];

  async function calculate() {
    if (busy || !canCalculate) return;
    const token = ++revision.current, key = inputKey;
    const controller = new AbortController(); computation.current = controller;
    oddsComputation.current?.abort(); setOddsBusy(false);
    setBusy(true); setResult(null); setOdds(null); setError("");
    const common = { board: request.spot.board, dead: cards(dead), method, samples: Number(samples), seed: Number(seed) };
    let path: string, payload: unknown;
    if (heroMode === "hand" && opponentMode === "hand") {
      path = "/api/equity/hand-vs-hand"; payload = { ...common,
        hero_cards: request.spot.hero_cards, opponent_cards: cards(opponentCards) };
    } else if (heroMode === "hand") {
      path = "/api/equity/hand-vs-range"; payload = { ...common,
        hero_cards: request.spot.hero_cards, opponent_range: request.opponent_range };
    } else if (opponentMode === "range") {
      path = "/api/equity/range-vs-range"; payload = { ...common,
        hero_range: request.hero_range, opponent_range: request.opponent_range };
    } else {
      path = "/api/equity/multiway"; payload = { ...common,
        players: [{ range: request.hero_range }, { cards: cards(opponentCards) }] };
    }
    try {
      const data = await requestJson<EquityResult>(path, payload, controller.signal);
      if (!controller.signal.aborted && token === revision.current && currentKey.current === key) { resultKey.current = key; setResult(data); }
    } catch (err) {
      if (!controller.signal.aborted && token === revision.current) setError(message(err));
    } finally {
      if (token === revision.current) setBusy(false);
    }
  }
  async function calculateOdds() {
    if (!hero || oddsBusy) return;
    const controller = new AbortController(), key = currentOddsKey.current; oddsComputation.current = controller;
    setOddsBusy(true); setOdds(null); setOddsError("");
    try {
      const data = await requestJson<PotOddsResult>("/api/equity/pot-odds", {
        pot: request.spot.pot, call: Number(call), equity: hero.equity,
        equity_interval: hero.uncertainty ? [hero.uncertainty.lower, hero.uncertainty.upper] : null,
      }, controller.signal);
      if (!controller.signal.aborted && key === currentOddsKey.current) { oddsKey.current = key; setOdds(data); }
    } catch (err) { if (!controller.signal.aborted) setOddsError(message(err)); }
    finally { if (!controller.signal.aborted) setOddsBusy(false); }
  }

  return <section className="equity-workspace" aria-label="Equity Analysis">
    <div className="study-card equity-panel"><div className="card-heading">
      <div><p className="eyebrow">EQUITY ANALYSIS</p><h2>Hand equity</h2></div>
      <span className="data-tag calculated">{busy ? "CALCULATING" : hero ? "CALCULATED" : "ON DEMAND"}</span></div>
      <p>Real showdown probabilities for explicit hands and assumed ranges. Equity is not GTO strategy.</p>
      <div className="equity-inputs">
        <label className="field">Hero equity input<select value={heroMode} onChange={e => setHeroMode(e.target.value as typeof heroMode)}>
          <option value="hand">Specific hero cards</option><option value="range">Hero range</option></select></label>
        <label className="field">Opponent equity input<select value={opponentMode} onChange={e => setOpponentMode(e.target.value as typeof opponentMode)}>
          <option value="range">Explicit opponent range</option><option value="hand">Specific opponent cards</option></select></label>
        {opponentMode === "hand" && <label className="field">Opponent hole cards<input value={opponentCards} placeholder="Qs Qd" onChange={e => setOpponentCards(e.target.value)} /></label>}
        <label className="field">Dead cards<input placeholder="Optional: 2s 3s" value={dead} onChange={e => setDead(e.target.value)} /></label>
        <label className="field">Calculation method<select aria-label="Calculation method" value={method} onChange={e => setMethod(e.target.value as EquityMethod)}>
          <option value="auto">Auto (bounded exact or Monte Carlo)</option><option value="exact">Exact enumeration</option><option value="monte_carlo">Monte Carlo estimate</option></select></label>
        <label className="field">Simulations<input type="number" min="100" max="10000" step="100" value={samples} onChange={e => setSamples(e.target.value)} /></label>
        <label className="field">Random seed<input type="number" min="0" max="4294967295" step="1" value={seed} onChange={e => setSeed(e.target.value)} /></label>
      </div>
      <div className="equity-context" aria-label="Equity inputs">
        <span>Hero: <b>{heroMode === "hand" ? request.spot.hero_cards.join(" ") || "select two cards" : "editable hero range"}</b></span>
        <span>Opponent: <b>{opponentMode === "hand" ? opponentCards || "select two cards" : needsAssumption ? "range not confirmed" : "explicit assumed range"}</b></span>
        <span>Board: <b>{request.spot.board.join(" ") || "preflop"}</b></span>
      </div>
      {needsAssumption && <div className="range-consent"><b>No calibrated range for this profile, position, and history.</b>
        <p>Profile statistics do not define an exact range. Edit the opponent matrix or deliberately adopt its displayed preview as an editable assumption.</p>
        <button className="text-button" disabled={!study || !Object.values(study.opponent_range.weights).some(w => w > 0)}
          onClick={() => study && onAdoptRange({ ...study.opponent_range.weights })}>Use displayed range as assumption</button>
      </div>}
      {error && <div role="alert" className="error-banner">{error}</div>}
      <button className="primary equity-calculate" disabled={busy || !canCalculate} onClick={() => void calculate()}>
        {busy ? "Calculating equity…" : "Calculate equity"}</button>
      <p className="field-hint">100–10,000 samples; at most 5,000 exact outcomes and 20,000 rank evaluations.
        No computation starts automatically. Edits to equity inputs clear prior results.</p>
      {visibleResult && hero && <div className="equity-results" aria-label="Equity results" role="status">
        <div className="equity-numbers"><div><span>Win probability</span><strong>{percent(hero.win_probability)}</strong></div>
          <div><span>Tie probability</span><strong>{percent(hero.tie_probability)}</strong></div>
          <div><span>Total equity</span><strong>{percent(hero.equity)}</strong></div></div>
        <p><b>{visibleResult.method === "exact" ? "Exact enumeration" : "Monte Carlo estimate"}</b> · {visibleResult.evaluated_outcomes.toLocaleString("en-US")} evaluated outcomes
          {visibleResult.valid_samples !== null ? ` · ${visibleResult.valid_samples.toLocaleString("en-US")} valid samples · seed ${visibleResult.seed}` : " · no sampling uncertainty"}</p>
        {hero.uncertainty && <p>95% simultaneous Hoeffding interval: {percent(hero.uncertainty.lower)}–{percent(hero.uncertainty.upper)}.
          Standard error: {percent(hero.uncertainty.standard_error)}. Sampling uncertainty only.</p>}
        <p>Unblocked combinations: hero {visibleResult.unblocked_combinations[0]}, opponent {visibleResult.unblocked_combinations[1]}.
          Joint collisions are removed separately.</p>
        <p className="field-hint">{visibleResult.distribution}. Uniform remaining runouts.
          All players reach showdown in one common pot; side pots and rake are excluded.
          An exact calculation is conditional on your range assumptions, not evidence they are calibrated.</p>
      </div>}
    </div>
    <section className="study-card odds-panel" aria-label="Pot odds and simplified call EV">
      <div className="card-heading"><h2>Pot odds & call EV</h2><span className="data-tag">SHOWDOWN ONLY</span></div>
      <label className="field">Current pot before calling (chips)<input readOnly value={request.spot.pot} /></label>
      <p className="field-hint">Includes the opponent's bet. Edit the Situation pot above to change this value.</p>
      <label className="field">Hero call amount (chips)<input type="number" min="0" max="100000000" step="1" value={call} onChange={e => setCall(e.target.value)} /></label>
      <p>Uses the calculated total equity. Assumes full showdown realization, no future betting, no rake,
        no additional contributions, and no separate side pots. This is not a general postflop action solver.</p>
      {oddsError && <div className="error-banner" role="alert">{oddsError}</div>}
      <button className="text-button" disabled={!hero || oddsBusy || !integer(call, 0, 100000000) || request.spot.pot + Number(call) === 0}
        onClick={() => void calculateOdds()}>{oddsBusy ? "Calculating pot odds…" : "Calculate pot odds"}</button>
      {visibleOdds && hero && <div aria-label="Pot odds results" role="status" className="odds-results">
        <p>Required break-even equity <strong>{percent(visibleOdds.required_equity)}</strong></p>
        <p>Simplified call EV <strong>{visibleOdds.call_ev.toFixed(2)} chips</strong></p>
        {visibleOdds.call_ev_interval && <p>Sampling interval for simplified EV: {visibleOdds.call_ev_interval[0].toFixed(2)} to {visibleOdds.call_ev_interval[1].toFixed(2)} chips.</p>}
        <p className="field-hint">{visibleOdds.explanation}</p>
      </div>}
    </section>
  </section>;
}
