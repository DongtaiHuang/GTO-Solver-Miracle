import type { GameState } from "../lib/types";
import { Card } from "./Card";
import { PlayerSeat, chips } from "./PlayerSeat";
export function PokerTable({ game }: { game: GameState }) {
  const winners = new Set(game.outcomes.flatMap(o => o.winners));
  return <div className="table-stage">
    <div className="table-felt"><div className="felt-line" /></div>
    <div className="table-center">
      <p className="table-brand">POKER STRATEGY LAB</p>
      <div className="pot-label">{game.street === "complete" ? "Settled pot" : "Total pot"}
        <strong>{chips(game.street === "complete" ? game.settled_pot : game.pot)} <small>chips</small></strong></div>
      <div className="board" aria-label="Community cards">
        {Array.from({ length: 5 }, (_, i) => <Card key={i} value={game.board[i]} />)}
      </div>
      <div className="street-label">{game.street === "complete" ? (game.showdown ? "Showdown" : "Hand complete") : game.street}</div>
    </div>
    {game.players.map(p => <PlayerSeat key={p.seat} player={p} hero={p.seat === game.hero}
      button={p.seat === game.button} winner={winners.has(p.seat)} />)}
  </div>;
}
