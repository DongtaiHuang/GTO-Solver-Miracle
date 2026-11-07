import type { GameState } from "../lib/types";
export function gameState(): GameState {
  return {
    hand_id: "test-hand", hand_number: 1, revision: 0, street: "preflop",
    button: 0, hero: 0, actor: 0, board: [], pot: 450, settled_pot: 0,
    big_blind: 100, effective_stack: 9900,
    players: ["You", "Alex", "Morgan", "Sam", "Jordan", "Casey"].map((name, seat) => ({
      seat, name, position: ["BTN", "SB", "BB", "UTG", "HJ", "CO"][seat],
      stack: 10000, bet: seat === 2 ? 100 : 0, status: seat === 0 ? "acting" : "waiting",
      cards: seat === 0 ? ["As", "Kh"] : null, effective_stack: 10000,
    })),
    legal: { actions: ["fold", "call", "raise", "all_in"], to_call: 100,
      min_raise_to: 200, max_raise_to: 10000, presets: { "33": 281, "50": 375, "75": 512, "100": 650 } },
    history: [{ sequence: 1, street: "preflop", seat: 2, name: "Morgan", action: "big_blind", chips: 100, raise_to: null }],
    outcomes: [], showdown: false,
  };
}
export function completedState(): GameState {
  const state = gameState();
  return { ...state, revision: 1, street: "complete", actor: null, showdown: true,
    board: ["2c", "3c", "4c", "5d", "9h"], pot: 0, settled_pot: 600,
    players: state.players.map(p => ({ ...p, stack: p.seat === 0 ? 10500 : 9900,
      cards: p.cards ?? ["Qd", "Jd"], status: "settled" })),
    legal: { actions: [], to_call: 0, min_raise_to: null, max_raise_to: 0, presets: {} },
    outcomes: [{ pot: 600, winners: [0], payouts: { "0": 600 } }],
  };
}
