# Task 004 — Real showdown equity

Task 004 adds independent showdown-equity calculations to Study. It does **not** implement GTO solving, strategic frequencies, equilibrium action EV, opponent-range calibration, or exploitative best responses. The Task 001 evaluator and game engine are unchanged.

## Using Study

1. Enter a legal board (0, 3, 4, or 5 cards) and, for a specific-hand calculation, two hero cards in Situation.
2. Edit the independent hero/opponent matrices. A class inclusion weight is an integer from 0% to 100%.
3. In Equity Analysis, choose specific hands or ranges, optional dead cards, Auto/Exact/Monte Carlo, sample count, and seed.
4. For a profile preview, explicitly choose **Use displayed range as assumption**, or edit the opponent matrix. A VPIP percentage or archetype alone never authorizes an equity calculation.
5. Click **Calculate equity**. It reports hero's sole-win probability, shared-win/tie probability, fractional pot equity, method, outcome/sample count, unblocked combinations, and sampled uncertainty.
6. Optionally enter the amount to call and click **Calculate pot odds**. The Situation pot must include the opponent bet and exclude hero's pending call.

An unsupported Standard GTO profile supplies no range. It must be manually configured; there is no automatic GTO-equity shortcut. Adopting a TAG/LAG/TP/LP preview records an **assumed** range, not an exact inference from VPIP or a calibrated range for a position/betting sequence. Changing profile parameters resets that adoption.

Calculations run only on explicit clicks. Changing equity inputs clears old results, aborts delivery of pending client responses, and requires another click. Changing only pot/call values preserves showdown equity and invalidates pot-odds results. Server computations already in progress finish within their bounded work budget; closing a browser request is not server-side cancellation.

The UI compares two players. The backend additionally supports two through six players. Trainer hidden cards remain hidden; specific opponent cards entered in Study are hypothetical input, not retrieved from the trainer.

## Computational separation

- `equity.py`: card/range expansion, probability model, exact enumeration, Monte Carlo, uncertainty, and simplified pot odds. It imports no FastAPI code.
- `equity_api.py`: strict typed input/output schemas, HTTP error mapping, and per-process admission control.
- `evaluator.evaluate`: the existing exact best-five-of-seven evaluator, reused unchanged for every ranking.
- `EquityAnalysis.tsx`: typed on-demand controls/results. The client does not implement hand ranking, equity, or EV formulas.

The GTO provider contracts remain separate and continue returning unavailable solver data. A real showdown calculation is not evidence of an optimal poker action.

## Range and blocker model

The existing matrix has 169 classes: 13 pairs × 6 combinations, 78 suited classes × 4, and 78 offsuit classes × 12 = 1,326 combinations before blockers.

Each positive class weight is assigned to **every individual combination** in that class. Thus AA at 50% gives each of its six combinations mass 50, not a total class mass of 50. Zero weights remove the class. Known board cards, dead cards, and all fixed player hands are removed from each ranged player's possible combinations.

`unblocked_combinations` is the integer support size of each player after those known-card blockers (one for a specific hand). It is not a weighted count and does not imply every retained combination is compatible with all other players' ranges. Mutual collisions are handled by the joint distribution. Empty individual supports and jointly impossible supports are rejected.

Cards use the existing canonical strings: ranks 23456789TJQKA and suits c/d/h/s. Duplicate cards anywhere in the board, fixed hands, or dead cards are invalid. A fixed hand overlapping a possible range combination blocks that combination rather than making the whole range invalid.

## Probability distribution

For player i, let w_i(h_i) be the weight of a specific two-card combination. Fixed hands have a single possible combination. For a tuple of player hands H:

```text
P(H) = product_i w_i(h_i) / Z    if all hands are pairwise card-disjoint
       0                        otherwise
Z = sum over valid tuples of product_i w_i(h_i)
```

All inputs are additionally conditioned on the visible board and declared dead cards. Multiplying every weight in one player's range by the same positive constant does not change the result.

Given a valid tuple H, the missing board cards are uniform over all unordered combinations from the remaining deck. Unknown burns are marginalized out. Every tuple removes the same number of cards, so the runout count is constant across valid tuples.

This is **not** hero-first sequential range sampling: choosing a weighted hero hand, then independently renormalizing the opponent range around it changes the marginal distribution. The implementation instead uses independent product proposals and rejects colliding tuples. Accepted tuples have exactly the distribution above.

An illustrative river check is hero range {AA:100, KK:100} against {AA:100} on 2c 3d 7h 8c Jd. There are 6 valid AA/AA tuples and 36 KK/AA tuples. Hero ties with probability 1/7 and has equity 1/14; an incorrect hero-first method would overcount AA/AA.

## Exact enumeration and Monte Carlo

**Auto** estimates a conservative outcome upper bound:

```text
product of unblocked support sizes × C(52 − board cards − dead cards − 2 × players, missing board cards)
```

If that bound is within both the exact-outcome cap and ranking-work cap, it enumerates every valid hand tuple and remaining runout, accumulating the tuple's product weight. Otherwise it samples. Explicit Exact requests above the bound are rejected with a message to use Monte Carlo; they never silently become estimates.

For Monte Carlo, a private `random.Random(seed)` chooses each player's combination by integer cumulative weight. The entire tuple is rejected on collisions. A uniform `random.sample` of the remaining deck supplies the runout; ordering does not affect the shared evaluator. No importance weights are needed for accepted samples. The simulator does not alter global random state.

Each outcome gives a player:
- 1 for a sole win;
- 1/k when among k tied winners;
- 0 otherwise.

The reported equity is the weighted mean of this share. Heads-up it equals P(win) + 0.5 × P(tie). Multiway tie probability is the probability the player shares the best hand; it is **not** automatically divided by total player count. Only the tied winners divide the pot. All equities sum to one, up to floating-point rounding.

`evaluated_outcomes` counts actual valid tuple/runout evaluations. `valid_samples` is null for Exact and the fulfilled requested count for Monte Carlo. `proposals` includes rejected Monte Carlo tuples. Requests that cannot fill the requested sample count within the proposal budget fail instead of reporting a misleading partial result.

Identical validated inputs and seeds produce identical results for this Python/runtime/algorithm version. Reproducibility across future Python or implementation changes is not promised. Exact results have no sampling uncertainty but still depend on ranges, assumptions, and ordinary floating-point arithmetic.

## Uncertainty

Let X be the player's fractional pot share, which lies in [0,1]. Sampled results return:
- Unbiased sample-variance standard error: sqrt(s² / N).
- A conservative simultaneous 95% Hoeffding interval across all P players:

```text
margin = sqrt(log(2P / 0.05) / (2N))
interval = [max(0, mean − margin), min(1, mean + margin)]
```

Hoeffding's bound plus the union bound gives simultaneous coverage for the P bounded means under independent accepted samples. It remains nondegenerate when every observed result is a win, loss, or fixed split. Standard error alone would incorrectly suggest certainty at a sampled boundary. The bounds measure **sampling uncertainty only**; they do not capture uncertainty about opponent ranges, actual future actions, or model calibration. They are not intervals for win probability, bluff frequency, or strategic EV.

## Simplified pot odds and call EV

With pot P **before hero calls**, already including the opponent's bet, call C, and calculated fractional equity E:

```text
Required equity = C / (P + C)
Simplified call EV = E × (P + C) − C
```

The denominator includes the call exactly once. Pot/call amounts must be nonnegative integer chip units, each at most 100,000,000, and P+C must be positive. Equity and optional ordered interval endpoints must be finite probabilities; the interval must contain E.

A supplied equity interval is propagated through the same increasing linear EV formula. The UI forwards the equity engine's interval, so sampled EV is not presented as exact. All results assume full showdown realization, no future betting, no rake, no further contributions, and **one common pot with no separate side-pot complications**. They do not determine a general postflop optimal action. Use the existing game engine for actual side-pot settlement.

## Typed API

Every endpoint is POST with application/json through the existing same-origin Next.js proxy.

| Endpoint | Required scenario fields |
| --- | --- |
| /api/equity/hand-vs-hand | hero_cards, opponent_cards (two cards each) |
| /api/equity/hand-vs-range | hero_cards, opponent_range: {weights: {...}} |
| /api/equity/range-vs-range | hero_range and opponent_range: {weights: {...}} |
| /api/equity/multiway | players: [{cards: [...]}, {range: {weights: {...}}}, ...], 2–6 entries |
| /api/equity/pot-odds | pot, call, equity; optional equity_interval: [lower, upper] |

Equity endpoints also accept board (default []), dead (default [], at most 40), method (auto/exact/monte_carlo), samples (default 2,000), and seed (default 42). A player specifies exactly one hand or range. Schema validation rejects unsupported counts, fractional weights, booleans used as integer counts, excessive sample requests, invalid options and unknown fields. Domain validation rejects invalid/duplicate cards, invalid board lengths, empty or impossible ranges, and insufficient remaining cards.

Responses list players in input order, with win/tie/loss probabilities, equity, and optional uncertainty; include method, outcome/sample/proposal counts, seed (null for Exact), unblocked supports, a string work upper bound, distribution, and assumptions. Large work estimates are strings to avoid JavaScript integer precision loss.

Error status:
- 400: invalid cards/ranges or pot-odds domain input.
- 422: invalid schema or deterministic work-budget violation.
- 429: another equity calculation is active; retry after it finishes.

No equity endpoint reads a trainer's hidden cards or accepts a profile as a substitute for explicit weights. Calculations are stateless, responses are private/no-store, and mutation Origin/JSON checks remain intact.

## Work and memory limits

- Maximum Monte Carlo samples: 10,000; minimum: 100.
- Maximum requested rank evaluations: 20,000 (samples × player count for Monte Carlo; conservative outcome bound × player count for Exact).
- Maximum exact outcomes: 5,000.
- Maximum product proposals: 200,000.
- Maximum compatibility-search visits: 50,000.
- Maximum per-calculation rank-cache entries: 4,096.
- One active equity job per backend process; concurrent jobs return 429. The proxy allows up to 30 seconds for equity routes.

A bounded compatibility search first proves at least one valid assignment. Some difficult range configurations can hit its work limit even if a compatible assignment exists; this returns an explicit work error, not a false claim of mathematical impossibility. Conservative bounds can also reject an Exact request whose true disjoint outcome count is smaller; Auto/Monte Carlo is the practical alternative.

The existing evaluator enumerates 21 five-card subsets and prioritizes correctness over specialized native performance. A calculation-local LRU cache reuses **the same evaluator**, especially on river range queries. Count limits bound work rather than promising wall-clock latency on all hardware. Large production workloads, distributed queues, and native evaluator optimization are future work. Server jobs are not asynchronously cancellable in this milestone.

## Benchmarks

Measured locally with Python 3.12.1 on Windows, median of three in-process repeats; 2,000 requested Monte Carlo samples and seed 42. These are observed measurements, not service guarantees:

| Case | Actual evaluated outcomes | Median seconds |
| --- | ---: | ---: |
| Specific AA vs KK, river Exact | 1 | 0.0002 |
| Specific AA vs KK, turn Exact | 44 | 0.0079 |
| Specific AA vs KK, flop Exact | 990 | 0.1875 |
| Specific AA vs KK, preflop Monte Carlo | 2,000 | 0.4014 |
| All 169 classes vs all 169, river Monte Carlo | 2,000 | 0.1180 |

Reproduce from backend:

```powershell
..\.venv\Scripts\python.exe benchmarks/equity_benchmark.py --repeats 3 --samples 2000
```

The script emits JSON with method, outcome count, runtime, Python version, and OS. Timings exclude HTTP/React startup overhead and depend on host load and cache reuse. Benchmark data is not used as strategy data or as a correctness oracle.

## Verification

Run the standard pytest/coverage, Ruff, mypy, frontend tests, TypeScript and production-build commands, plus `npm run test:e2e`.

Tests include analytically derived exact river/turn/flop fixtures, royal flushes, wheels/quads, heads-up and multiway splits, individual/known-card blockers, product-conditioned weighted ranges, global RNG isolation, seeded reproducibility, Monte Carlo agreement with enumeration, uncertainty behavior at boundaries, limits and invalid inputs, concurrency admission/release, pot odds, UI range adoption, stale-response invalidation, and real desktop/mobile equity/EV flows.

The earlier Trainer/Study tests continue running. No GTO strategies, frequencies, exploitative best-response EV, calibrated opponent ranges, equity-realization model, or detailed hand analyzer have been added. Docker remains unverified locally for this change.
