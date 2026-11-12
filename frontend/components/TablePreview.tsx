import type { ProfileConfig } from "../lib/study-types";
export function profileLabel(id: ProfileConfig["id"]) {
  return id === "standard_gto" ? "Standard GTO" : id.toUpperCase();
}
export function TablePreview({opponents}:{opponents:ProfileConfig[]}) {
  return <div className="table-stage preview-table" aria-label="Six-player table before dealing">
    <div className="table-felt"><div className="felt-line"/></div>
    <div className="table-center"><h2>Your seat is ready.</h2><p>100 BB · 50 / 100 blinds</p></div>
    {Array.from({length:6},(_,i)=><div className={`seat seat-${i}`} key={i}>
      <div className="seat-info"><strong>{i===0?"You":"Seat "+i}</strong>
      <div className="seat-status">{i===0?"Hero":profileLabel(opponents[i-1].id)}</div></div></div>)}
  </div>;
}
