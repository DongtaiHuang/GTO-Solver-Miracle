import type { Player } from "../lib/types";
import { Card } from "./Card";
export const chips = (amount: number) => amount.toLocaleString("en-US");
export function PlayerSeat({ player, hero, button, winner }: {
  player: Player; hero: boolean; button: boolean; winner: boolean;
}) {
  return <section className={`seat seat-${player.seat} ${player.status === "acting" ? "seat-active" : ""}
    ${player.status === "folded" ? "seat-folded" : ""} ${hero ? "seat-hero" : ""} ${winner ? "seat-winner" : ""}`}
    aria-label={`${player.name}, ${player.position}`}>
    <div className="seat-cards">{[0, 1].map(i =>
      <Card key={i} value={player.cards?.[i]} hidden={!player.cards} />)}</div>
    <div className="seat-info">
      <div className="seat-name"><span>{player.name}</span><span className="position">{player.position}</span></div>
      <strong>{chips(player.stack)} <small>chips</small></strong>
      <div className="seat-status">{winner ? "Winner" : player.status}</div>
    </div>
    {button && <span className="dealer" title="Dealer button">D</span>}
    {player.bet > 0 && <div className="seat-bet"><span>●</span> {chips(player.bet)}</div>}
  </section>;
}
