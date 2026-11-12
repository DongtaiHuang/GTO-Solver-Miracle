import Link from "next/link";
import type { GameState } from "../lib/types";
import { chips } from "./PlayerSeat";
export function ShowdownResult({ game }: { game: GameState }) {
  const net = game.players[game.hero].stack - 100*game.big_blind;
  return <section className="showdown-result" aria-label="Hand result" role="status">
    <div><p className="eyebrow">{game.showdown ? "SHOWDOWN" : "UNCONTESTED"}</p>
      <h2>{net > 0 ? "You win" : net < 0 ? "You lost chips" : "Even hand"}
        <span className={net >= 0 ? "positive" : "negative"}> {net > 0 ? "+" : ""}{chips(net)} chips</span></h2></div>
    <p>Settled pot <strong>{chips(game.settled_pot)} chips</strong> · Hero final stack {chips(game.players[game.hero].stack)}</p>
    <ul>{game.outcomes.map((outcome, i) => <li key={i}>
      Pot {i + 1} · {chips(outcome.pot)} → {Object.entries(outcome.payouts).map(([seat, payout]) =>
        `${game.players[Number(seat)].name} ${chips(payout)}`).join(" / ")}
    </li>)}</ul>
    <Link className="button-link" href="/analyzer?from=trainer">Review This Hand</Link>
  </section>;
}
