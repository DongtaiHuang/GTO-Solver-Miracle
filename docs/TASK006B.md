# Task 006B — Restricted river best responses

In Study choose a reviewed river decision, query it, then select an opponent profile. The response panel reports incremental chips separately for each hero combo. Edits specify an opponent's probability of taking the sized action. Its complement determines checking or folding. BTN's free fold has probability zero. Higher betting rates increase aggression and lower rates increase passivity. The two BTN inputs independently specify value betting with AcAd and bluffing with 5c4c. The BB inputs independently specify calling with KhQh and KsJs. All probabilities are conditional on the represented information set.

| Model | BTN value bet | BTN bluff | BB KQ call | BB KJ call |
|---|---:|---:|---:|---:|
| TAG | .90 | .20 | .50 | .35 |
| LAG | .95 | .75 | .70 | .60 |
| TP | .55 | .05 | .35 | .20 |
| LP | .60 | .25 | .90 | .85 |

These qualitative presets are direct river assumptions. VPIP and PFR do not determine any river probability. Standard GTO reads the opponent's exact paired Task 006A combination policy. Selecting a new profile restores its preset.

## Computation

For pot P, bet B, and BTN showdown share s, a check yields sP. A called bet yields C = s(P+2B)−B to BTN and P−C to BB. A fold to a bet yields P to BTN and zero to BB. For BTN, average each candidate action over compatible BB combos using their normalized range weights. Betting against a BB combo with call rate c gives (1−c)P+cC. For BB, multiply each compatible BTN combo's original reach by its probability of betting, normalize, and then average P−C to value a call. A zero denominator means the decision is unreachable under the model.

For each hero combo maximize the averaged action EV. This order prevents a decision from depending on hidden opponent cards. Retain the equilibrium mix renormalized over maximizing actions within 1e-10 chip tolerance, or split equally if those actions had zero baseline mass. Dotting each hero distribution with the same action values gives baseline and response EV against the fixed model. Gain is their difference. Cost against equilibrium is baseline EV minus response EV evaluated against the original paired equilibrium opponent, including equilibrium reach conditioning. This measures the specified equilibrium opponent, not worst-case counter-exploitation. A zero cost can occur when an equilibrium opponent makes hero indifferent.

## Coverage and reproduction

Both 275- and 550-chip trees and both acting seats from [Task 006A](TASK006A.md) are supported. The API accepts the complete Task 005 scenario and requires an exact published match and paired reviewed equilibrium record. Both records use schema 1.0 and the fixed ranges specified by the Task 006A abstraction. The public session trainer can display conditional feedback when board, history, positions, pot, effective stack and hero combo match. The user chooses the restricted tree; the table still plays its original heuristic policies. Feedback assumes the stated solver ranges. It does not inspect opponent hole cards or estimate a population strategy.

For an analytical check select river-550-btn-v1 and the LP profile, then set both BB call rates to zero. The bluff wins 550 by betting and zero by checking. Its equilibrium mix (50% betting in the pot-sized tree) earns 275, so always betting gains 275 chips against this model. Use the usual backend pytest, Ruff, mypy, frontend test, typecheck, build and Playwright commands in README. The numerical response calculation uses the same terminal utilities as the offline Task 006A solver and needs no numerical optimizer at runtime.
