import type { OpponentProfile, ProfileConfig, ProfileParameters, StudyRequest, StudyResult } from "../lib/study-types";
import { parameterLabels } from "../lib/study-types";
export const profileFixtures: OpponentProfile[] = [
  { id: "standard_gto", name: "Standard GTO", description: "No validated solution is connected.",
    parameters: null, source: "unavailable", solver_backed: false },
  ...([
    ["tag", "Tight Aggressive (TAG)", [24,20,7,55,60,45,45,40,45,35]],
    ["lag", "Loose Aggressive (LAG)", [38,30,12,35,72,32,70,62,62,65]],
    ["tp", "Tight Passive (TP)", [18,9,3,70,30,62,22,15,45,12]],
    ["lp", "Loose Passive (LP)", [45,12,4,38,40,25,28,18,85,18]],
  ] as [ProfileConfig["id"], string, number[]][]).map(([id, name, values]) => ({
    id, name, description: `${name}: configurable initial assumptions.`,
    parameters: Object.fromEntries(Object.keys(parameterLabels).map((key, i) => [key, values[i]])) as ProfileParameters,
    source: "initial_assumptions" as const, solver_backed: false as const,
  })),
];
export function studyFixture(request?: StudyRequest): StudyResult {
  const p = profileFixtures.find(p => p.id === request?.opponent.id) ?? profileFixtures[1];
  const opponent = { ...p, parameters: request?.opponent.parameters ?? p.parameters };
  const weights = request?.opponent_range?.weights ?? (opponent.id === "standard_gto" ? {} : { AA: 100, KQs: 50 });
  const summary = (weights: Record<string, number>, source: string) => ({
    weights, weighted_combos: 10, available_weighted_combos: 8, source,
  }); // Synthetic UI counts only; backend exact-combo tests verify arithmetic.
  return {
    game_state_id: "ui-contract-fixture", context_source: "hypothetical",
    trainer_hand_id: null, trainer_revision: null,
    spot: request?.spot ?? { game_format: "6-max NLHE cash", starting_stack_bb: 100,
      hero_position: "BTN", opponent_position: "BB", hero_cards: [], board: [],
      street: "preflop", pot: 150, bet_sizes: [], history: "" },
    opponent, hero_range: summary(request?.hero_range.weights ?? {}, "editable_manual"),
    opponent_range: summary(weights, request?.opponent_range ? "editable_manual" : "modeled_assumption"),
    texture: { availability: "not_applicable", paired: null, max_suit_count: 0, rank_span: null,
      explanation: "Visible card counts only." },
    providers: ["precomputed_gto", "statistical_opponent_model", "custom_cfr"].map(source => ({
      game_state_id: "ui-contract-fixture", legal_actions: null, frequencies: null,
      ev_per_action: null, hand_equity: null, source, calculation_method: "No validated dataset configured",
      availability: source === "statistical_opponent_model" ? "model_only" : "unavailable",
      confidence: source === "statistical_opponent_model" ? "unvalidated" : "not_applicable",
      assumptions: ["Inclusion weights are not action frequencies."],
      explanation: source === "statistical_opponent_model" ? opponent.description : "GTO solution unavailable",
    })),
  };
}
