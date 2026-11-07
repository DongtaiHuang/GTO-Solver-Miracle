import type { Action, Street } from "./types";
export type ProfileId = "standard_gto" | "tag" | "lag" | "tp" | "lp";
export const parameterLabels = {
  vpip: "VPIP", pfr: "PFR", three_bet: "3-bet", fold_to_three_bet: "Fold to 3-bet",
  flop_cbet: "Flop continuation bet", fold_to_flop_cbet: "Fold to flop c-bet",
  turn_aggression: "Turn aggression", river_aggression: "River aggression",
  calling_tendency: "Calling tendency", bluffing_tendency: "Bluffing tendency",
} as const;
export type ProfileParameters = Record<keyof typeof parameterLabels, number>;
export interface ProfileConfig { id: ProfileId; parameters?: ProfileParameters | null }
export interface OpponentProfile extends ProfileConfig {
  name: string; description: string; source: "initial_assumptions" | "unavailable"; solver_backed: false;
}
export const positions = ["UTG", "HJ", "CO", "BTN", "SB", "BB"] as const;
export interface StudySpot {
  game_format: "6-max NLHE cash"; starting_stack_bb: 100;
  hero_position: typeof positions[number]; opponent_position: typeof positions[number];
  hero_cards: string[]; board: string[]; street: Street; pot: number; bet_sizes: number[]; history: string;
}
export interface StudyRequest {
  spot: StudySpot; opponent: ProfileConfig; hero_range: { weights: Record<string, number> };
  opponent_range: { weights: Record<string, number> } | null;
}
export interface RangeSummary {
  weights: Record<string, number>; weighted_combos: number; available_weighted_combos: number; source: string;
}
export interface StrategyResponse {
  game_state_id: string; legal_actions: Action[] | null;
  frequencies: Partial<Record<Action, number>> | null;
  ev_per_action: Partial<Record<Action, number>> | null; hand_equity: number | null;
  source: string; calculation_method: string;
  availability: "unavailable" | "model_only" | "available";
  confidence: "not_applicable" | "unvalidated" | "validated"; assumptions: string[]; explanation: string;
}
export interface StudyResult {
  game_state_id: string; spot: StudySpot; opponent: OpponentProfile;
  hero_range: RangeSummary; opponent_range: RangeSummary;
  texture: { availability: "calculated" | "not_applicable"; paired: boolean | null;
    max_suit_count: number; rank_span: number | null; explanation: string };
  providers: StrategyResponse[]; context_source: "hypothetical" | "trainer_snapshot";
  trainer_hand_id: string | null; trainer_revision: number | null;
}
