import { rangeMatrix } from "../lib/ranges";
import type { StrategyActionView, ClassStrategy } from "../lib/strategy-types";

export function actionColor(action: StrategyActionView, index: number): string {
  return { fold: "#596578", check: "#609ac2", call: "#80b997", bet: "#d1a164",
    raise: "#c97e68", all_in: "#b17ca7" }[action.action] ?? (index % 2 ? "#ab9cce" : "#8cad9c");
}
export function actionLabel(action: StrategyActionView): string {
  return action.action.replaceAll("_", " ") + (action.amount !== null ?
    ` ${action.action === "bet" || action.action === "raise" || action.action === "all_in" ? "to " : ""}${action.amount}` : "");
}
export function StrategyMatrix({ classes, actions, selected, onSelect, demo }: {
  classes: ClassStrategy[]; actions: StrategyActionView[]; selected: string;
  onSelect: (hand: string) => void; demo: boolean;
}) {
  const byClass = new Map(classes.map(c => [c.hand_class,c]));
  return <div className="matrix-scroll"><div className="range-matrix strategy-matrix" role="group"
    aria-label={demo ? "Synthetic strategy matrix" : "GTO strategy matrix"}>
    {rangeMatrix.flat().map(hand => {
      const record = byClass.get(hand);
      return <button type="button" key={hand} className={`strategy-cell ${hand === selected ? "strategy-selected" : ""}`}
        aria-label={`${hand} ${record ? `strategy coverage ${record.represented_combos}/${record.unblocked_combos}` : "strategy unavailable"}`}
        aria-pressed={hand === selected} onClick={() => onSelect(hand)}>
        <span className="strategy-segments" aria-hidden="true">{record && actions.map((action,i) =>
          <i key={action.key} style={{ width: `${(record.frequencies[action.key] ?? 0) * 100}%`,
            backgroundColor: actionColor(action,i) }} />)}</span><b>{hand}</b>
      </button>;
    })}
  </div></div>;
}
export function FrequencyChart({ frequencies, actions, label }: {
  frequencies: Record<string, number> | null; actions: StrategyActionView[]; label: string;
}) {
  return <div className="frequency-chart" aria-label={label}>{frequencies ? actions.map((action,i) =>
    <div className="frequency-row" key={action.key}><div><span>{actionLabel(action)}</span>
      <b>{((frequencies[action.key] ?? 0) * 100).toFixed(1)}%</b></div>
      <div className="frequency-track"><i style={{ width: `${(frequencies[action.key] ?? 0) * 100}%`, backgroundColor: actionColor(action,i) }} /></div>
    </div>) : <p className="unavailable-value">GTO solution unavailable</p>}</div>;
}
