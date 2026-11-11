# Task 007 — Hand History Analyzer

Open /analyzer, expand **Enter or edit hand**, set the six names and stacks, choose hero, and enter cards separated by spaces (As Kd). Validate the setup, then record actions using the buttons for the current actor. Bet and raise amounts are total street commitments. The action buttons supply the engine's actual call cost or all-in target. Add a complete flop, turn or river as necessary and validate again. You can enter a full board in advance or leave a hand incomplete. Undo removes the last recorded decision. Optional showdown payouts are checked against the engine.

## Format and replay

Version 1.0 JSON stores six position-keyed seats (BTN, SB, BB, UTG, HJ, CO), each with name, positive integer starting stack and optional two cards. It stores the hero position, small and big blinds, board in deal order, and ordered actions. Each action records position, street, action and amount. Check/fold take null, call takes the incremental cost, and bet/raise/all-in take the total street target. The optional initial_pot verifies the sum of posted blinds (including short stacks). Six occupied seats, a half-size small blind, zero antes and zero dead money are supported.

POST /api/analyzer/replay validates the whole history and returns the initial snapshot plus one snapshot after each action. Snapshot i contains the state before action i. Its prior_action_count identifies the exact prefix of the submitted action list. Pot, bets, contributions, acting seat, statuses and legal sizing come from the original Holdem engine. The engine deck places supplied cards at their real deal and burn offsets. Remaining internal deck slots follow deterministic deck order. Unknown cards are never returned or used to determine a contested award. A contested finish missing any live hand or board card leaves contributions in the pot and marks settlement unresolved. An uncontested finish needs no opponent cards. Verified settlements use the original side-pot, tie and odd-chip rules. Non-hero cards become visible only at contested showdown and only for live hands.

The timeline selects the state immediately before the clicked action. Street controls jump to the first recorded decision state on a street. An all-in runout has no intervening betting decisions. At partial street boundaries, action recording waits for that street's board.

## Analysis

The panel displays call odds (call divided by the eligible pot after calling, capped at the caller's total contribution in each opponent's stack) and visible board texture. Click Calculate hero equity to call the existing hand-vs-weighted-range API against the explicitly selected heads-up assumption. These estimates do not account for additional live opponents. The analyzer compares replayed positions, board, stacks, street, pot, blinds and ordered history with reviewed public strategy scenarios. Select a specific source's range and sizing abstraction before querying the existing exact strategy endpoint. Solver and model action EV use incremental chips. Individual EV loss is available only for represented known cards and a recorded action with a complete validated EV comparison. Unsupported histories produce no decision score. The existing restricted river response panel uses the selected profile's conditional river assumptions. Equity and model calculations run separately.

## Trainer and persistence

Review This Hand opens /analyzer?from=trainer. GET /api/analyzer/trainer requires the trainer session cookie and a completed current hand. Conversion uses the existing filtered GameView, actual street events and published payouts. Stored opponent hands are restricted to legitimately revealed cards. Complete the review or save the JSON before replacing the trainer hand.

Save in this tab uses browser sessionStorage. A named save overwrites the same name. Reopen validates the stored JSON. Closing the browser tab normally clears saves; use Export JSON for durable storage. A duplicated tab may inherit an initial copy under browser sessionStorage semantics. Exported files include the entered hero and showdown cards. Imported files must be application JSON, at most 1 MiB. The service validates unknown fields, duplicate keys, cards, turn order, amounts and payout claims before replacing the current replay. There is no server-side hand archive or external poker-site parser.

## Verification

Run pytest, Ruff and mypy in backend, and npm test, npm run typecheck, npm run build and npm run test:e2e from the repository root with the environment described in README. Analyzer tests exercise exact river matches, unsupported states, all-in side pots, ties, incomplete boards, hidden cards, trainer session ownership, UI entry, manual equity, model changes, file transfer and tab-local reopen.
