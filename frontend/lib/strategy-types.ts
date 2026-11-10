export type StrategyMode = "validated_gto" | "synthetic_demo";
export interface SizedStrategyAction { action: string; amount: number | null }
export interface BettingEvent extends SizedStrategyAction { street: string; position: string }
export interface StrategyScenario {
  schema_version: "1.0"; game_format: "6-max NLHE cash"; players: 6;
  starting_stacks: Record<string, number>; small_blind: number; big_blind: number; ante: 0;
  hero_position: string; opponent_position: string; effective_stack: number; pot: number;
  street: string; board: string[]; dead_cards: string[]; history: BettingEvent[];
  legal_actions: SizedStrategyAction[];
  abstraction: { tree_id: string; range_model_id: string; card_model: string; rake_model: string;
    action_semantics: string; assumptions: string[] };
}
export interface StrategyScenarioIndex {
  scenarios: { solution_id: string; scenario_id: string; kind: string; scenario: StrategyScenario; label: string }[];
  message: string;
}
export interface StrategyActionView extends SizedStrategyAction { key: string }
export interface ComboStrategy {
  cards: [string,string]; hand_class: string; reach_weight: number;
  frequencies: Record<string, number>; action_ev: Record<string, number> | null;
}
export interface ClassStrategy {
  hand_class: string; represented_combos: number; unblocked_combos: number; reach_mass: number;
  frequencies: Record<string, number>; action_ev: Record<string, number> | null;
}
export interface StrategySource {
  solution_id: string; kind: string; solver_identifier: string; solver_version: string;
  source_name: string; source_url: string; license_name: string; license_url: string;
  redistribution: string; validation_status: string; validation_methodology: string;
  limitations: string[]; checked_at: string; imported_at: string; approval_status: string;
  mathematical_verification: string;
}
export interface StrategyResult {
  scenario_id: string; status: "available" | "synthetic_demo" | "unavailable"; is_gto_recommendation: boolean;
  message: string; scenario: StrategyScenario; actions: StrategyActionView[];
  source: StrategySource | null; combinations: ComboStrategy[]; classes: ClassStrategy[];
  frequencies: Record<string, number> | null; action_ev: Record<string, number> | null;
  represented_combos: number; unblocked_combos: number; aggregation_method: string;
}
