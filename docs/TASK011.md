# Task 011 — Multi-street best responses

Select **ts-root-v1** in Study, query the strategy, choose TAG in Opponent comparison, and click **Calculate full-tree response**. Expand the policy editor to inspect an opponent information set or override a single combo. The optional best-response matrix uses the selected model's reached combo weights. The primary matrix continues to show the published equilibrium record. Analyzer offers the same computation after replay identifies an exact supported abstraction; a known hand filters the displayed decisions.

## Game and complete reference

The game is the [Task 009](TASK009.md) two-street abstraction: BB acts first on Kd 7h 2s Tc against BTN, 550 in the pot, 9,750 remaining each after a six-seat, 100 BB single-raised preflop pot and a checked flop. Each street allows check or a half-pot bet, then fold or call. Both eight-combo ranges and their weights are fixed in the reference. Sixty compatible deals each have 44 legal rivers. The original card evaluator, payoff arrays, deal probabilities, hand order and public histories are compiled from TurnGame. Blocked rivers have zero joint mass. The API handles either seat as hero, determined by the selected decision.

The packaged gzip artifact contains the full 1,500-iteration average policy (including off-path continuations), cached root-relative BTN terminal utility matrices, chance masses and row indices. Its uncompressed size is 730,934 bytes. Generation first reproduces every published Task 009 record and approval hash, then compares all covered combo probabilities with the regenerated full policy, verifies the original game value and gap, and binds each supported solution ID to its reviewed document hash. Runtime checks the artifact SHA-256, exact canonical scenario, document hash, version and role before evaluation. Canonical public histories preserve turn lines even when river pots coincide. The API exposes decisions at the 28 published nodes. It evaluates the entire tree including unpublished rivers.

## Conditional policy

The reference version is **ts009-average-1500-v1**. An editor key such as **turn/check/check/9d/check** denotes the checked-through turn, public 9d river, and BB check. The fixed public prefix, board and acting seat follow from the exact reference. A row selects one opponent combo and probabilities for both actions available in that tree. A free fold omitted by the solver has probability zero; the editable unopened row uses check/bet. Forced or unavailable actions cannot receive mass. Reject blocked combos, conflicting seat, duplicate override keys, unknown history, extra fields, nonfinite or negative values and sums differing from one by more than 1e-12.

Standard GTO uses the unchanged full reference. TAG, LAG, TP and LP initialize the second action (bet 275) on the opponent's first unopened turn decision to 40%, 75%, 15% and 25% respectively for each of its eight combos. BB opens at turn; BTN opens after BB checks. These are deliberately narrow illustrative hypotheses. All other nodes inherit the reference. User row overrides take precedence, including any compatible river. Results list changed rows with both distributions. Sensitivity recomputes up to three models with explicit opening rates, normally base and ±15 percentage points clipped to [0,100], retaining the same sparse overrides. Each result shows its own optimal action mix, chip values and gain; two variants can agree. These comparisons are deterministic scenarios.

Study's observation panel can suggest a provisional label or manual override after explicit user selection. Counts, sample sizes and credible intervals remain available there. Adoption selects a hypothesis and still requires a calculation. Observed VPIP, PFR and aggression never determine private-combo frequencies. No observation archive, private cards or player identifier is sent to the strategy endpoint.

## Backward induction, units and reach

The recursion returns one counterfactual chip value per hero hand. At each terminal, sum over compatible opponent hands using joint chance mass times the opponent's realization probability. BB utility is 550 minus BTN utility, equivalent to a zero-sum game after subtracting a constant. At an opponent decision, propagate each conditional action probability into that opponent hand's realization weight and sum children. At a public deal node, sum river children (their joint masses already contain 1/44). At a hero node choose the better action for each hero hand **after** averaging unseen opponent hands and, on the turn, future rivers. Exact ties retain the reference distribution. A separate pass evaluates that entire chosen strategy against the equilibrium opponent.

Write B for paired equilibrium policies, M for the fixed model, and R for the optimized hero policy. Reported root gain is V(R,M) − V(B,M). Paired-equilibrium cost is V(B,B) − V(R,B). These are signed ex-ante chip differences on the original 550-chip turn pot. Cost measures performance against that particular reference opponent, rather than an adversarial re-solve. With an approximate benchmark, a small best-response gain against B is expected.

Decision values normalize the counterfactual actions by compatible opponent/chance mass and add back the actor's sunk investment. Joint decision reach also includes the hero's own earlier realization probabilities. Report separate baseline/model, response/model, baseline/equilibrium and response/equilibrium values. A zero-reach comparison returns null at that information set. Conditional gains and costs require both compared policies to reach the decision; they generally differ from root differences. Matrix aggregation weights each reached model-response combo by its actual joint reach.

## Worked result and verification

At ts-root-v1 with BB as hero and default TAG, BTN bets 275 with probability .40 after the turn check with every compatible combo, and otherwise follows the equilibrium continuation policy. BB equilibrium earns 297.201946 chips against equilibrium and 306.440297 against this TAG model. The optimized BB strategy earns 350.309397 against TAG, an improvement of **43.869100 chips**. Against the paired equilibrium it earns 285.132721, a cost of **12.069226 chips**. For KhQh, the baseline bets about 36.07%; the response checks 100%. These numbers are conditional on the specified hypothetical policy.

With the unchanged equilibrium opponent, optimal BTN and BB root EVs reproduce the Task 009 independent best responses (252.807639137 and 297.214851918 chips). The sum of their deviation gains equals the original 0.022491055-chip full gap. Numerical tests compare this pure-Python implementation against the independent NumPy Task 009 best_response traversal for both roles and evaluate the generated strategy against the paired equilibrium via TurnGame.traverse, to absolute tolerance 1e-8 chips. A small bluff fixture verifies the 275-chip gain against an always-folding opponent and indifference when equally likely hidden callers have opposite responses. Other tests cover invalid inputs, blocked cards, sparse edits, unreachable branches, sensitivity, exact identity and request isolation.

## API and performance

POST /api/strategy/multistreet-policy takes solution_id, scenario, reference_version and opponent (BTN/BB). It returns equilibrium editor rows keyed by public history and opponent combo. POST /api/strategy/multistreet adds hypotheses (one to three), each with name, profile, optional opening_bet in [0,1], and up to 32 overrides of the form {node, combo, probabilities}. The response identifies the source reference, changed rows, root EV comparisons and conditional decisions. Unknown/mismatched policies return 422. Payloads exceeding 64 KiB return 413 before JSON parsing. Two simultaneous response calculations per app process are allowed; excess requests return 429. The reference is process-cached, hash-pinned and decompression is bounded to 1 MiB. Only the fixed compiled tree is traversed; user input cannot introduce nodes, iteration budgets or larger ranges. Every model and its returned policy is request-local.

A local five-run benchmark with three hypotheses and 32 overrides each measured median 0.120 s and maximum 0.141 s per comparison, excluding network and JSON serialization. A separate cold run including artifact loading traced 4,890,669 bytes peak with tracemalloc. Timing varies by machine. The traced measurement excludes interpreter baseline and does not impose a process RSS limit. The fixed artifact, topology, row and concurrency caps bound application working storage.

Use Python 3.12 with the backend installed; only offline reproduction and numerical tests require Task 009's NumPy 2.4.6 and SciPy 1.15.3 environment:

```sh
python tools/build_response_reference.py --verify
python tools/benchmark_multistreet.py
python -m pytest -q tools
```

Omit --verify to regenerate the artifact, then review any digest difference before changing the pinned reference in multistreet.py. Existing Task 006B river comparisons have their own endpoint and validated tree boundaries. No new equilibrium solver, automatic empirical policy fitting, or generalized exploit recommendations are provided for other trees.
