import type { StrategyActionView } from "../lib/strategy-types";
import { actionColor, actionLabel } from "./StrategyMatrix";

export function HandActions({actions, frequencies, ev}:{
  actions:StrategyActionView[];
  frequencies:Record<string,number>;
  ev:Record<string,number>|null;
}) {
  return <table className="hand-actions" aria-label="Selected hand action frequencies and EV">
    <thead><tr><th>Action</th><th>Frequency</th><th title="Expected value in chips from this decision">EV · chips</th></tr></thead>
    <tbody>{actions.map(action=>{
      const p=frequencies[action.key], value=ev?.[action.key];
      return <tr key={action.key}><th scope="row">{actionLabel(action)}</th><td>
        <span>{(p*100).toFixed(1)}%</span><span className="action-meter" aria-hidden="true">
          <i style={{width:p*100+"%",background:actionColor(action,actions)}}/></span>
      </td><td>{value===undefined?"—":value.toFixed(3)}</td></tr>;
    })}</tbody>
  </table>;
}
