const suits: Record<string, string> = { c: "♣", d: "♦", h: "♥", s: "♠" };
export function Card({ value, hidden = false }: { value?: string; hidden?: boolean }) {
  if (!value) return <div className={hidden ? "card card-back" : "card card-empty"}
    aria-label={hidden ? "Hidden card" : "Undealt card"}>{hidden ? "◆" : ""}</div>;
  const red = value[1] === "h" || value[1] === "d";
  return <div className={`card ${red ? "card-red" : ""}`} aria-label={value}>
    <span>{value[0] === "T" ? "10" : value[0]}</span><b>{suits[value[1]]}</b>
  </div>;
}
