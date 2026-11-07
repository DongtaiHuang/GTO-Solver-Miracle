export type EquityMethod = "auto" | "exact" | "monte_carlo";
export interface EquityUncertainty {
  standard_error: number; lower: number; upper: number; confidence_level: number; interval_method: string;
}
export interface PlayerEquity {
  win_probability: number; tie_probability: number; loss_probability: number;
  equity: number; uncertainty: EquityUncertainty | null;
}
export interface EquityResult {
  method: "exact" | "monte_carlo"; players: PlayerEquity[]; evaluated_outcomes: number;
  valid_samples: number | null; proposals: number; seed: number | null;
  unblocked_combinations: number[]; work_upper_bound: string; distribution: string; assumptions: string[];
}
export interface PotOddsResult {
  required_equity: number; call_ev: number; call_ev_interval: [number, number] | null; explanation: string;
}
