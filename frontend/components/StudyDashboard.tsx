"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { requestJson } from "../lib/api";
import { handClasses } from "../lib/ranges";
import { positions } from "../lib/study-types";
import type { ProfileConfig, StudyRequest, StudyResult, StudySpot } from "../lib/study-types";
import { useProfiles } from "../lib/useProfiles";
import { ProfileEditor } from "./ProfileEditor";
import { RangeMatrix } from "./RangeMatrix";
import { StrategyPanels } from "./StrategyPanels";
import { EquityAnalysis } from "./EquityAnalysis";
import {OpponentIntelligence} from "./OpponentIntelligence";
import { StrategyWorkspace } from "./StrategyWorkspace";

interface Form {
  hero_position: StudySpot["hero_position"]; opponent_position: StudySpot["opponent_position"];
  hero_cards: string; board: string; street: StudySpot["street"]; pot: string; bet_sizes: string; history: string;
}
const initialForm: Form = { hero_position: "BTN", opponent_position: "BB", hero_cards: "",
  board: "", street: "preflop", pot: "150", bet_sizes: "", history: "" };
const parseCards = (text: string) => text.trim().split(/[\s,]+/).filter(Boolean).map(
  card => card[0].toUpperCase() + card.slice(1).toLowerCase());

export function StudyDashboard() {
  const { profiles, error: profileError } = useProfiles();
  const [viewMode, setViewMode] = useState<"strategy" | "ranges">("strategy");
  const [form, setForm] = useState<Form>(initialForm);
  const [opponent, setOpponent] = useState<ProfileConfig>({ id: "tag" });
  const [heroWeights, setHeroWeights] = useState<Record<string, number>>({ AA: 100, KK: 100, QQ: 100, AKs: 100 });
  const [opponentWeights, setOpponentWeights] = useState<Record<string, number> | null>(null);
  const [activeRange, setActiveRange] = useState<"hero" | "opponent">("opponent");
  const [selected, setSelected] = useState("AKs");
  const [result, setResult] = useState<StudyResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [locked, setLocked] = useState(false);
  const [error, setError] = useState("");
  const [importError, setImportError] = useState("");
  const importing = useRef(false);
  const request = useMemo<StudyRequest>(() => ({
    spot: { ...form, game_format: "6-max NLHE cash", starting_stack_bb: 100,
      hero_cards: parseCards(form.hero_cards), board: parseCards(form.board), pot: Number(form.pot),
      bet_sizes: form.bet_sizes.trim() ? form.bet_sizes.trim().split(/[\s,]+/).map(Number) : [] },
    opponent, hero_range: { weights: heroWeights },
    opponent_range: opponentWeights === null ? null : { weights: opponentWeights },
  }), [form, opponent, heroWeights, opponentWeights]);

  async function importCurrent() {
    importing.current = true; setLocked(true); setLoading(true); setImportError(""); setError("");
    try {
      const data = await requestJson<StudyResult>("/api/study/current");
      const spot = data.spot;
      setForm({ hero_position: spot.hero_position, opponent_position: spot.opponent_position,
        hero_cards: spot.hero_cards.join(" "), board: spot.board.join(" "), street: spot.street,
        pot: String(spot.pot), bet_sizes: spot.bet_sizes.join(", "), history: spot.history });
      setOpponent({ id: data.opponent.id, parameters: data.opponent.parameters });
      setHeroWeights(data.hero_range.weights); setOpponentWeights(null); setResult(data);
    } catch (err) {
      setImportError(err instanceof Error ? err.message : "Could not import the trainer hand.");
      setLocked(false);
    } finally { importing.current = false; setLoading(false); }
  }
  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("from") === "trainer") { setViewMode("ranges"); void importCurrent(); }
  }, []);
  useEffect(() => {
    if (viewMode !== "ranges" || locked || importing.current) return;
    setResult(null); setLoading(true); setError("");
    const controller = new AbortController();
    const timer = setTimeout(() => {
      requestJson<StudyResult>("/api/study", request, controller.signal).then(data => {
        if (!controller.signal.aborted) { setResult(data); setLoading(false); }
      }).catch(err => {
        if (!controller.signal.aborted) {
          setError(err instanceof Error ? err.message : "Unable to analyze this spot."); setLoading(false);
        }
      });
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [request, locked, viewMode]);

  function edit<K extends keyof Form>(key: K, value: Form[K]) {
    setLocked(false); setForm(previous => ({ ...previous, [key]: value }));
  }
  const weights = activeRange === "hero" ? heroWeights : opponentWeights ?? result?.opponent_range.weights ?? {};
  function updateRange(next: Record<string, number>) {
    setLocked(false);
    if (activeRange === "hero") setHeroWeights(next); else setOpponentWeights(next);
  }
  return <main className="study-page study-lab">
    <header className="lab-toolbar"><h1>Study</h1>
      <div className="study-view-switch" role="group" aria-label="Study workspace mode">
        <button aria-pressed={viewMode === "strategy"} onClick={() => setViewMode("strategy")}>Strategy visualization</button>
        <button aria-pressed={viewMode === "ranges"} onClick={() => setViewMode("ranges")}>Range editing & equity</button>
      </div>
      <button className="import-button" onClick={() => { setViewMode("ranges"); void importCurrent(); }} disabled={viewMode === "ranges" && loading}>Import trainer hand ↗</button>
    </header>
    {viewMode === "ranges" && <div className="study-banner"><span className="status-dot" /><div><b>GTO solution unavailable</b>
      <p>Model ranges and inspect card facts today. GTO strategy frequencies and solver action EV are unavailable. Calculate showdown equity separately against explicit assumptions.</p></div>
      <span className="data-tag unavailable">EXACT MATCH REQUIRED</span></div>}
    {(error || importError || profileError) && <div className="error-banner" role="alert">{error || importError || profileError}</div>}
    {viewMode === "ranges" && <div className="profile-comparison" role="group" aria-label="Compare opponent archetypes">
      {profiles.map(profile => {
        const params = opponent.id === profile.id ? opponent.parameters ?? profile.parameters : profile.parameters;
        return <button key={profile.id} aria-pressed={opponent.id === profile.id}
          onClick={() => { setLocked(false); setOpponent({ id: profile.id, parameters: profile.parameters });
            setOpponentWeights(null); }}>
          {profile.id === "standard_gto" ? "Standard GTO" : profile.id.toUpperCase()}
          <small>{params ? `VPIP ${params.vpip}% · PFR ${params.pfr}%` : "Not solver-backed"}</small>
        </button>;
      })}</div>}
    {viewMode === "strategy" ? <StrategyWorkspace profiles={profiles} opponent={opponent}
      onOpponentChange={next => { setOpponent(next); setOpponentWeights(null); }} /> : <>
    <section className="study-card spot-panel" aria-label="Study situation">
      <div className="card-heading"><h2>Situation</h2><span className="data-tag">{locked ? "TRAINER SNAPSHOT" : "EDITABLE HYPOTHETICAL"}</span>
        <span className="spot-format">6-max NLHE cash · 100 BB · chips</span></div>
      <div className="fixed-configuration">
        <label className="field">Game format<input readOnly value="6-max NLHE cash" /></label>
        <label className="field">Starting stack<input readOnly value="100 BB" /></label>
      </div>
      <div className="spot-fields">
        <label className="field">Hero position<select aria-label="Hero position" value={form.hero_position} onChange={e => edit("hero_position", e.target.value as Form["hero_position"])}>
          {positions.map(position => <option key={position}>{position}</option>)}</select></label>
        <label className="field">Opponent position<select aria-label="Opponent position" value={form.opponent_position} onChange={e => edit("opponent_position", e.target.value as Form["opponent_position"])}>
          {positions.map(position => <option key={position}>{position}</option>)}</select></label>
        <label className="field">Street<select aria-label="Street" value={form.street} onChange={e => edit("street", e.target.value as Form["street"])}>
          {["preflop", "flop", "turn", "river", "complete"].map(street => <option key={street}>{street}</option>)}</select></label>
        <label className="field">Hero hole cards<input placeholder="As Kd" value={form.hero_cards} onChange={e => edit("hero_cards", e.target.value)} /></label>
        <label className="field">Community cards<input placeholder="Qs Jh 2c" value={form.board} onChange={e => edit("board", e.target.value)} /></label>
        <label className="field">Pot (chips)<input type="number" min="0" step="1" value={form.pot} onChange={e => edit("pot", e.target.value)} /></label>
      </div>
      <details className="history-input"><summary>Bet sizes & action history</summary><div className="history-fields">
        <label className="field">Bet sizes (chips)<input placeholder="100, 300" value={form.bet_sizes} onChange={e => edit("bet_sizes", e.target.value)} /></label>
        <label className="field">Betting action history<textarea rows={4} maxLength={100000} value={form.history} placeholder="Describe the full-hand action sequence…"
          onChange={e => edit("history", e.target.value)} /></label></div></details>
      <p className="field-hint">{locked ? "An ownership-checked snapshot of your trainer session. Editing any field creates a hypothetical spot." :
        "Free-form history is context, not a validated betting replay. Legal actions are available only from an untouched trainer snapshot."}</p>
    </section>
    <div className="study-workspace"><div className="study-main-column">
      <section className="study-card range-panel"><div className="card-heading"><div><p className="eyebrow">RANGE EXPLORER</p><h2>169 ways to start.</h2></div>
        <span className="data-tag modeled">EDITABLE MODEL</span></div>
        <div className="range-tabs" role="group" aria-label="Range editor">
          <button aria-pressed={activeRange === "hero"} onClick={() => setActiveRange("hero")}>Hero range</button>
          <button aria-pressed={activeRange === "opponent"} onClick={() => setActiveRange("opponent")}>Opponent range</button>
          <span aria-live="polite">{loading ? "Updating…" : result ? "Model ready" : "Check situation"}</span></div>
        <div className="matrix-scroll"><RangeMatrix weights={weights} selected={selected} onSelect={hand => {
          setSelected(hand); updateRange({ ...weights, [hand]: weights[hand] ? 0 : 100 });
        }} /></div>
        <div className="range-legend"><span>Diagonal: pairs</span><span>Above: suited</span><span>Below: offsuit</span></div>
        <div className="range-edit-row"><label className="field">{selected} inclusion weight (%)
          <input aria-label="Selected hand inclusion weight" type="number" min="0" max="100" step="1"
            value={weights[selected] ?? 0} onChange={e => updateRange({ ...weights, [selected]: Number(e.target.value) })} /></label>
          <button className="text-button" onClick={() => updateRange({})}>Clear range</button>
          <button className="text-button" onClick={() => updateRange(Object.fromEntries(handClasses.map(hand => [hand, 100])))}>Select all</button></div>
        <p className="field-hint">Cell fill is inclusion weight, never action frequency.
          Hero starts with a small editable example range. Modeled opponent width comes from VPIP and an unvalidated rank ordering.</p>
      </section>
      <div className="range-summaries">{(["hero", "opponent"] as const).map(side => {
        const range = result?.[side === "hero" ? "hero_range" : "opponent_range"];
        return <section className="study-card" key={side} aria-label={`${side} range summary`}>
          <div className="card-heading"><h2>{side === "hero" ? "Hero" : "Opponent"} range</h2><span className="data-tag calculated">COMBO COUNT</span></div>
          <strong className="range-count">{range && !loading ? range.available_weighted_combos.toLocaleString("en-US") : "—"} <small>available weighted combos</small></strong>
          <p>{range && !loading ? `${range.weighted_combos} / 1,326 before blockers · ${range.source.replaceAll("_", " ")}` : "Waiting for a valid configuration"}</p>
          <p className="field-hint">{side === "hero" ? "Excludes community-card blockers." : "Excludes community cards and known hero cards."}</p></section>;
      })}</div>
    </div><aside className="study-card profile-panel"><div className="card-heading"><div><p className="eyebrow">OPPONENT LAB</p><h2>Change the lens.</h2></div></div>
      <ProfileEditor profiles={profiles} value={opponent} onChange={next => {
        setLocked(false); setOpponent(next); setOpponentWeights(null);
      }} />
      <p className="field-hint">Changing profile parameters rebuilds the modeled opponent range and replaces its manual edits.
        Defaults describe this model only, not universal player statistics.</p>
    </aside></div>
    <EquityAnalysis request={request} study={result} onAdoptRange={next => {
      setLocked(false); setOpponentWeights(next);
    }} />
    <StrategyPanels result={result} pending={loading} />
    </>}
    <OpponentIntelligence onHypothesis={id=>{setOpponent({id});setOpponentWeights(null);setViewMode("strategy");}}/>
  </main>;
}
