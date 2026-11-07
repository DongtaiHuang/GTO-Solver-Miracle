import type { OpponentProfile } from "./study-types";
export type Action = "fold" | "check" | "call" | "bet" | "raise" | "all_in";
export type Street = "preflop" | "flop" | "turn" | "river" | "complete";
export interface Player {
  seat: number; name: string; position: string; stack: number; bet: number;
  status: string; cards: string[] | null; effective_stack: number;
}
export interface LegalActions {
  actions: Action[]; to_call: number; min_raise_to: number | null;
  max_raise_to: number; presets: Record<string, number>;
}
export interface HistoryEntry {
  sequence: number; street: Street; seat: number | null; name: string;
  action: string; chips: number; raise_to: number | null;
}
export interface Outcome { pot: number; winners: number[]; payouts: Record<string, number> }
export interface GameState {
  hand_id: string; hand_number: number; revision: number; street: Street;
  button: number; hero: number; actor: number | null; board: string[];
  pot: number; settled_pot: number; big_blind: number; effective_stack: number;
  players: Player[]; legal: LegalActions; history: HistoryEntry[];
  outcomes: Outcome[]; showdown: boolean; opponents?: OpponentProfile[];
}
