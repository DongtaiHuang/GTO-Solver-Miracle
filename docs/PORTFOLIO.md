# MIRACLE — poker study and decision feedback

MIRACLE connects a playable six-seat no-limit hold'em table to a replayable hand history and a solver-backed decision library. A player can move from a supported decision to its hand combination, compare action values, and practice the same spot against an explicit opponent assumption.

## Engineering decisions

- The Next.js frontend uses a same-origin proxy to FastAPI. The backend validates integer-chip betting, all-ins and settlement. Analyzer replays ordered actions and respects the information visible to the player at each decision.
- The strategy catalog matches canonical public histories, board, ranges and exact sizes. Offline river and turn-to-river solvers export reviewed combo-level strategies. CFR+ averages strategies over iterations; a separate best-response evaluation measures the restricted game's convergence gap. Exact and Monte Carlo showdown equity are available independently.
- Opponent observations count opportunities and expose uncertainty. Modeled turn and river policies specify what an opponent does at their own information sets; Hero's best response averages over hidden cards and future runouts. Archetype labels are hypotheses. Practice records distinguish retry history, conditional EV loss and equilibrium cost.
- PostgreSQL stores private hands, evidence and versioned attempts. Google identity verification, revocable session digests, owner-scoped queries, explicit imports and revision checks protect cross-device saves. Tests cover financial-unit arithmetic in chips, independent numerical evaluations, two-user isolation, restore behavior and browser workflows.

## Three-minute demonstration

1. In Study, select ts-root-v1 and query the exact turn. Inspect BB's KhQh combination, action mix, EV and provenance.
2. Open Training Center for that combo. Compare the equilibrium grade with the fixed TAG model, submit a choice, then retry. Explain why the two losses differ.
3. Start a Trainer hand, finish it and follow Review This Hand into Analyzer. Step to a Hero decision and identify which cards are public. Most arbitrary decisions have no matching solver record.
4. Show a saved record using a disposable test account only after authentication has been verified. Otherwise demonstrate tab-local export and explain the persistence boundary.

## Résumé bullet options

- Built a Next.js/FastAPI poker study platform linking six-player gameplay, deterministic hand replay and combination-specific practice across 37 reviewed solver decisions.
- Implemented and tested restricted turn-to-river CFR+ analysis over 60 compatible private-hand assignments and 44 legal rivers per assignment, with independent best-response evaluation.
- Integrated owner-scoped PostgreSQL storage and revocable Google-authenticated sessions, with regression coverage for access isolation, duplicate imports, migration and database recovery.

[Solver methodology](TASK009.md) · [Security review](TASK014B.md) · [Release evidence](RELEASE_V1.md)
