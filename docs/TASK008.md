# Task 008 — Expanded heads-up river solve

In Study select **cfr-river-root-v1** for BTN's decision, or **cfr-river-bet275-v1** for BB's response. Each of the two bet sizes has a distinct raise-response record. In Hand Analyzer, select the expanded abstraction at the matching decision. Five published nodes have combo frequencies, chip EVs and provenance. The original four restricted-tree records still support the Task 006B opponent response panel.

## Model and information

The public prefix is the Task 006A game: 6 occupied seats, stacks 10,000, blinds 50/100, no ante or rake. UTG, HJ and CO fold, BTN raises to 250, SB folds, BB calls. Board Kd 7h 2s Tc 9d checks through to BTN on the river. Pot 550; both have 9,750 behind. BTN checks or bets 275 or 550. BB can fold, call or raise to 1,650 total. Facing a raise BTN can fold or call the increment (1,375 or 1,100). The exported legal schema includes folding when checking is free; its frequency and incremental EV are zero.

The two weighted, manually specified ranges are in tools/expanded_ranges.json. These encode a study assumption about reaching the river. Initial joint chance is proportional to the product of weights on disjoint hole-card pairs. The board is fixed; all combos must avoid it. Four of 64 assignments are blocked. Discarding blocked deals and renormalizing induces different marginal probabilities for different combos. The normalized joint matrix is used for every chance calculation.

Each public history has one strategy row per acting player's own combo; columns are the node's legal actions. Board, ranges and abstraction are fixed for a solver instance. An opponent's private cards index payoff arrays but cannot index the deciding player's strategy. The implementation enumerates the finite river tree and all compatible deals without sampling. No random seed is required.

BTN root-relative payoff on a matched showdown investment x is s(550+2x)−x where showdown share s is 0, 1/2 or 1. BB folding yields 550 to BTN; BTN folding to a raise loses its original bet. BB payoff is 550 minus BTN payoff. Public action EV is expressed from the current decision, adding back the acting player's previous river investment. Positive conditional reach records are exported with joint node/hand mass for range aggregation.

## Algorithm and accuracy

Alternating CFR+ updates one player's cumulative regrets per pass. For each own combo and legal action, integrate continuation payoff over the joint deal distribution multiplied by the opponent's realization probability. Subtract that combo's current mixed action value, add the resulting regrets, and clip at zero. Regret matching normalizes positive regrets and uses uniform play when none are positive. The deployed average accumulates iteration number × own realization probability × action probability. The second player sees the first player's updated policy on its pass. [Tammelin, Solving Large Imperfect Information Games Using CFR+](https://arxiv.org/abs/1407.5042)

For the average profile, a separate traversal maximizes each player's counterfactual action value per own combo, working backward through the tree. The reported gap is the maximum BTN payoff against fixed BB minus the minimum BTN payoff against fixed BTN. This equals the sum of the two unilateral deviation gains; half this number is the common two-player exploitability convention. Tests cross-check both best-response values against exhaustive pure contingent plans on a smaller tree. The implementation caches hand ranks and terminal matrices and never constructs the normal-form strategy matrix. Cost per pass scales with public tree size times the number of private-hand pairs. There is no approximation from pruning.

At 4,000 iterations, the expanded BTN value was **227.99626511 chips** and the measured full gap was **0.00955011 chips** (about 0.00174% of the pot). This accuracy applies only to the stated ranges, board and tree.

| Reference bet | CFR+ value | Absolute value difference from HiGHS | Full gap | Max frequency difference | Max action EV difference |
|---|---:|---:|---:|---:|---:|
| 275 | 366.66666157 | 0.00000510 | 0.01681172 | 0.00008728 | 0.07200931 |
| 550 | 412.49999141 | 0.00000859 | 0.00001718 | 0.00000006 | 0.00002291 |

Frequency comparison uses each BTN combo and the mean call rate over strategically equivalent BB bluff-catchers. Action EV comparison uses individual check, bet, and call values (fold yields zero). Generation first checks both old LP games: full gap ≤0.5 chips, value error ≤0.25 chips, frequency error ≤0.005 and action EV error ≤2 chips. The expanded export requires a full gap ≤1 chip. The original HiGHS records reproduced independently.

## Bounded benchmark

Windows local run using 1,000 iterations of the same two-size/raise tree and prefixes of the supplied ranges. Wall time includes construction, training and accuracy evaluation. Peak traced allocation measures a separate construction, one training iteration and report using Python tracemalloc; it excludes interpreter baseline, untracked native allocations and process RSS. Array shapes are constant across iterations.

| Combos per player | Seconds | Peak traced bytes | Information sets | Compatible deal-terminal pairs | Full gap, chips |
|---:|---:|---:|---:|---:|---:|
| 2 | 0.454 | 19,546 | 10 | 36 | 0.04556775 |
| 4 | 0.448 | 20,602 | 20 | 117 | 0.00170600 |
| 8 | 0.457 | 33,778 | 40 | 540 | 0.02217578 |

The 4,000-iteration expanded training and report took 1.46 seconds in the first local run. Nine terminal vectors are visited per pass (two training passes per iteration); the 540 distinct compatible deal-terminal payoffs are reused. The evaluator ranks each private combo once during construction. Timings depend on hardware.

## Reproduction and integration

In the project Python 3.12 environment, install the existing editable backend and offline numerical dependencies (SciPy 1.15.3, NumPy 2.4.6). From the root:

```sh
python tools/solve_river.py --bet 275 --verify
python tools/solve_river.py --bet 550 --verify
python -m pytest -q tools/test_river_cfr.py
python tools/solve_expanded.py --verify
python tools/benchmark_river.py
```

Omit --verify to regenerate the expanded artifact with a fresh UTC timestamp. Verification reuses the stored timestamp and compares all exported records. Exact floating-point serialization is intended for the same numerical environment. The version 1.0 dataset passes the existing replay, rights, normalization and content-bound approval checks. Full ranges and tree assumptions accompany each record; changed range weights change the range identifier. The existing exact strategy lookup serves precomputed data with no optimizer in the web request. The two numerical libraries are offline dependencies. Flop/turn solving, arbitrary board lookup, unrestricted NLHE, and opponent-specific best responses on the expanded tree remain outside this milestone.
