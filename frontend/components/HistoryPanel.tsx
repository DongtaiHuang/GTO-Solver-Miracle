import type { HistoryEntry } from "../lib/types";
import { chips } from "./PlayerSeat";
export function HistoryPanel({ entries }: { entries: HistoryEntry[] }) {
  return <aside className="history-panel"><div className="panel-title"><h2>Hand history</h2><span>{entries.length} events</span></div>
    <ol aria-label="Action history">{entries.map(entry => <li key={entry.sequence}>
      <span className="history-number">{String(entry.sequence).padStart(2, "0")}</span>
      <div><span className="history-street">{entry.street}</span>
        <p><b>{entry.name}</b> {entry.action.replaceAll("_", " ")}
          {entry.chips > 0 && <> · {chips(entry.chips)} chips</>}
          {entry.raise_to !== null && <> (to {chips(entry.raise_to)})</>}</p></div>
    </li>)}</ol>
  </aside>;
}
