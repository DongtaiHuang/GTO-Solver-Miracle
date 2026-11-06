export default function Home() {
  return (
    <main>
      <p className="eyebrow">POKER STRATEGY LAB / TASK 001</p>
      <h1>A foundation for<br />understanding the game.</h1>
      <p className="intro">An independent, deterministic No-Limit Texas Hold’em engine.
        Rules and settlement come first.</p>
      <section aria-label="Game configuration">
        <article><strong>6-max</strong><span>Table format</span></article>
        <article><strong>100 BB</strong><span>Starting stacks</span></article>
        <article><strong>50 / 100</strong><span>Blinds in integer chips</span></article>
      </section>
      <aside><h2>Engine foundation</h2><p>Dealing, legal actions, minimum raises, all-ins,
        side pots, street progression, seven-card evaluation, and showdown settlement.</p>
        <p>This initial frontend is a project shell. Interactive play and strategy analysis
          are outside Task 001. No solver or GTO recommendations are included.</p></aside>
    </main>
  );
}
