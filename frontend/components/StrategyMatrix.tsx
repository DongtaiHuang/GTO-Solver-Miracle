import { rangeMatrix } from "../lib/ranges";
import type { StrategyActionView, ClassStrategy } from "../lib/strategy-types";

export function actionColor(action: StrategyActionView, actions: StrategyActionView[]): string {
  if (action.action === "bet" || action.action === "raise") {
    const sizes = actions.filter(a => a.action === action.action).sort((a,b) => a.amount! - b.amount!);
    if (sizes.length > 1) {
      const fraction = sizes.findIndex(a => a.key === action.key) / (sizes.length - 1);
      return `hsl(${action.action === "bet" ? 38 : 12} 62% ${70 - 30 * fraction}%)`;
    }
  }
  return { fold: "#596578", check: "#609ac2", call: "#80b997", bet: "#d1a164",
    raise: "#c97e68", all_in: "#b17ca7" }[action.action] ?? "#8cad9c";
}
export function actionLabel(action: StrategyActionView): string {
  return action.action.replaceAll("_", " ") + (action.amount !== null ?
    ` ${action.action === "bet" || action.action === "raise" || action.action === "all_in" ? "to " : ""}${action.amount}` : "");
}
export function StrategyMatrix({ classes, actions, selected, onSelect, demo, label }: {
  classes: ClassStrategy[]; actions: StrategyActionView[]; selected: string;
  onSelect: (hand: string) => void; demo: boolean; label?: string;
}) {
  const byClass = new Map(classes.map(c => [c.hand_class,c]));
  return <div className="matrix-scroll"><div className="range-matrix strategy-matrix" role="group"
    aria-label={label??(demo ? "Synthetic strategy matrix" : "GTO strategy matrix")}>
    {rangeMatrix.flat().map((hand,index) => {
      const record = byClass.get(hand);
      return <button type="button" key={hand} className={`strategy-cell ${hand === selected ? "strategy-selected" : ""}`}
        aria-label={`${hand} ${record ? `strategy coverage ${record.represented_combos}/${record.unblocked_combos}` : "strategy unavailable"}`}
        tabIndex={hand===selected?0:-1} data-covered={Boolean(record)}
        title={record ? actions.map(a=>actionLabel(a)+": "+(record.frequencies[a.key]*100).toFixed(1)+"%").join(" · ") : hand+" · No coverage"}
        onKeyDown={e=>{
          const steps:Record<string,number>={ArrowLeft:-1,ArrowRight:1,ArrowUp:-13,ArrowDown:13,Home:-index,End:168-index};
          if(!(e.key in steps))return;
          e.preventDefault();
          const next=Math.max(0,Math.min(168,index+steps[e.key]));
          const button=e.currentTarget.parentElement?.querySelectorAll("button")[next];
          button?.focus(); onSelect(rangeMatrix.flat()[next]);
        }} aria-pressed={hand === selected} onClick={() => onSelect(hand)}>
        <span className="strategy-segments" aria-hidden="true">{record && actions.map((action) =>
          <i key={action.key} style={{ width: `${(record.frequencies[action.key] ?? 0) * 100}%`,
            backgroundColor: actionColor(action,actions) }} />)}</span><b>{hand}</b>
      </button>;
    })}
  </div></div>;
}
export function FrequencyChart({ frequencies, actions, label }: {
  frequencies: Record<string, number> | null; actions: StrategyActionView[]; label: string;
}) {
  return <div className="frequency-chart" aria-label={label}>{frequencies ? actions.map((action) =>
    <div className="frequency-row" key={action.key}><div><span>{actionLabel(action)}</span>
      <b>{((frequencies[action.key] ?? 0) * 100).toFixed(1)}%</b></div>
      <div className="frequency-track"><i style={{ width: `${(frequencies[action.key] ?? 0) * 100}%`, backgroundColor: actionColor(action,actions) }} /></div>
    </div>) : <p className="unavailable-value">GTO solution unavailable</p>}</div>;
}
