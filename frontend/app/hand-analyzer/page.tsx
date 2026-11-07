import Link from "next/link";
export default function HandAnalyzerPage() {
  return <main className="study-page"><header className="study-header"><div><p className="eyebrow">HAND ANALYZER</p>
    <h1>A place for the complete story.</h1><p>Detailed hand review is reserved for a future milestone.</p></div></header>
    <section className="study-card analyzer-placeholder"><span className="analyzer-symbol">≡</span>
      <h2>Hand review workspace</h2><p>Importing hand histories, replay analysis, and solver-backed comparisons are not implemented.</p>
      <p>You can already open a current or completed trainer hand in Study to inspect its visible state and modeled ranges.</p>
      <Link className="button-link" href="/trainer">Open Trainer</Link></section></main>;
}
