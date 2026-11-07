import type { StudyResult } from "../lib/study-types";
export function StrategyPanels({ result, pending }: { result: StudyResult | null; pending: boolean }) {
  const baseline = result?.providers.find(p => p.source === "precomputed_gto");
  return <div className="analysis-panels">
    <section className="study-card"><div className="card-heading"><h2>Strategy frequencies</h2><span className="data-tag unavailable">UNAVAILABLE</span></div>
      <p className="unavailable-value">GTO solution unavailable</p><p>No validated strategy source is connected.</p>
      <div className="placeholder-bars" aria-hidden="true"><i /><i /><i /></div>
      <p className="field-hint">Range inclusion weights are not action frequencies.</p></section>
    <section className="study-card"><div className="card-heading"><h2>Action EV</h2><span className="data-tag unavailable">UNAVAILABLE</span></div>
      <p className="unavailable-value">GTO solution unavailable</p><p>EV per action will appear only with a validated calculation.</p>
      <div className="empty-metric">— <small>chips / action</small></div></section>
    <section className="study-card texture-panel"><div className="card-heading"><h2>Board texture</h2>
      <span className="data-tag calculated">{pending ? "UPDATING" : result?.texture.availability === "calculated" ? "CALCULATED" : "NO BOARD"}</span></div>
      {result && !pending && result.texture.availability === "calculated" ? <>
        <dl className="texture-values"><div><dt>Paired ranks</dt><dd>{result.texture.paired ? "Yes" : "No"}</dd></div>
          <div><dt>Largest suit count</dt><dd>{result.texture.max_suit_count}</dd></div>
          <div><dt>Rank span (ace high)</dt><dd>{result.texture.rank_span}</dd></div></dl>
        <p>{result.texture.explanation}</p></> : <p>Enter a valid flop, turn, or river to calculate visible-card features.</p>}
    </section>
    <section className="study-card explanation-panel"><div className="card-heading"><h2>Strategic explanations</h2><span className="data-tag modeled">MODEL CONTEXT</span></div>
      {result && !pending ? <>
        <p>{result.providers.find(p => p.source === "statistical_opponent_model")?.explanation}</p>
        <ul>{result.providers.find(p => p.source === "statistical_opponent_model")?.assumptions.map(a => <li key={a}>{a}</li>)}</ul>
        <p className="field-hint">{baseline?.calculation_method}. Custom CFR: not implemented.
          No mathematically optimal action or exploitative best response is being recommended.</p>
        <p className="source-id">State {result.game_state_id} · {result.context_source.replaceAll("_", " ")}
          {result.trainer_revision !== null ? ` · revision ${result.trainer_revision}` : ""}</p>
        <p className="field-hint">Legal actions: {baseline?.legal_actions === null ? "unavailable for manually edited spots" :
          baseline?.legal_actions?.length ? baseline.legal_actions.join(", ") : "none (hand complete)"}.</p>
      </> : <p>{pending ? "Updating model context…" : "Configure a valid spot to inspect its assumptions and sources."}</p>}
    </section>
  </div>;
}
