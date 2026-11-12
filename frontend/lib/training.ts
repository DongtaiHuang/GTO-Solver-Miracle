export const archiveKey = "miracle.training.v1";
export const trainingApi = "/api/strategy/training/";
export type Exercise = {
  solution_id: string;
  scenario_id: string;
  version: string;
  combo: string;
};
export type Prompt = Exercise & {
  position: string;
  street: string;
  board: string[];
  pot: number;
  blind: number;
  actions: string[];
  history: string[];
  assumptions: string[];
  solver: string;
  accuracy: string;
};
export type Hypothesis = {
  name: string;
  profile: string;
  opening_bet?: number | null;
  overrides?: {
    node: string;
    combo: string;
    probabilities: Record<string, number>;
  }[];
};
export type Submission = Exercise & {
  action: string;
  hypothesis: Hypothesis | null;
};
export type Feedback = {
  status: "graded" | "ungraded";
  reason: string;
  frequencies: Record<string, number> | null;
  action_ev: Record<string, number> | null;
  best: string[];
  loss: number | null;
  loss_bb: number | null;
  response: Record<string, number> | null;
  model_gain: number | null;
  equilibrium_cost: number | null;
};
export type Attempt = {
  retry: boolean;
  origin: "practice" | "review";
  id: string;
  session: string;
  time: string;
  submission: Submission;
  feedback: Feedback;
  street: string;
  position: string;
};
export type Archive = { version: "1"; attempts: Attempt[] };
export type Report = Record<
  string,
  {
    count: number;
    graded: number;
    total_bb: number | null;
    average_bb: number | null;
  }
>;
export function policyKey(h: Hypothesis | null) {
  return h
    ? JSON.stringify([
        h.profile,
        h.opening_bet ?? null,
        (h.overrides ?? [])
          .map((o) => [o.node, o.combo, Object.entries(o.probabilities).sort()])
          .sort(),
      ])
    : "equilibrium";
}
export function spot(p: Exercise) {
  return [p.scenario_id, p.combo, p.version].join("/");
}
export function practiceUrl(
  source: string,
  scenario: string,
  combo: string,
  action?: string,
  review?: string,
) {
  const query = new URLSearchParams({ source, scenario, combo });
  if (action && review) {
    query.set("action", action);
    query.set("review", review);
  }
  return "/training?" + query;
}
export function selectIndex(length: number, seed: number) {
  return Math.floor(
    (((Math.imul(seed, 1664525) + 1013904223) >>> 0) / 4294967296) * length,
  );
}
