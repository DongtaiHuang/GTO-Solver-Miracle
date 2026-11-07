# Task 003 — Study and opponent modeling

## Branch dependency

Task 003 is developed on `codex/task-003-strategy-dashboard`, directly based on Task 002 commit `9cd1fea92586a251ad722d144ce1b07edcafb414` (`codex/task-002-poker-trainer`). The local main at branch creation contained Task 001 only. Task 003 therefore depends on Task 002 and includes its implementation in any comparison against that older main. No branches have been pushed or merged automatically.

## Navigation and use

- **Study** (`/`) is the default landing page. Configure a six-max cash spot, inspect/edit either range, compare archetypes, and view data availability.
- **Trainer** (`/trainer`) retains the working table. Configure five opponent seats before New Hand. Active hands keep their original configuration. Configuration is restored with the browser session.
- **Hand Analyzer** (`/hand-analyzer`) is a clearly labeled future workspace; no hand-history parser or replay analyzer is implemented.

The existing development commands are unchanged. Start FastAPI on 127.0.0.1:8000 and Next.js on localhost:3000; the frontend proxies the permitted API endpoints.

## Data categories

| Category | Available now | Meaning |
| --- | --- | --- |
| Calculated | Class combination counts, blockers, weighted counts, paired-board flag, suit count, high-ace rank span | Exact arithmetic over supplied visible cards and user/model weights |
| Modeled | Archetype parameters and a generated starting range | Editable initial assumptions, not observed statistics or equilibrium data |
| Unavailable | GTO action frequencies, action EV, hand equity, exploitative best responses, CFR results | No validated dataset, optimizer, equity enumeration, or simulation is connected |

Every missing equilibrium result is labeled **GTO solution unavailable**. Empty Standard GTO ranges mean unspecified, not a recommendation to fold every hand. Editing a range while that profile is selected creates a manual range, never a GTO solution.

The hero begins with a small manual example range (AA, KK, QQ, AKs). It is not advertised as a positional opening chart. Position, history, or board changes do not infer solver ranges or perform Bayesian action-history conditioning.

## Inputs and transfer from Trainer

Study accepts the fixed format (6-max NLHE cash) and starting stack (100 BB), hero/opponent positions, zero or two hero cards, community cards, street, pot and bet sizes in integer chips, and a free-form action-history text. Backend validation rejects duplicate/unknown cards, inconsistent street/board lengths, identical positions, negative/fractional chips, unknown fields, and invalid profile/range values.

Use **Open this hand in Study** in Trainer, or **Import trainer hand** in Study. The backend reads the owning session and transfers only the public game view: hero cards, visible board, positions, pot (settled total at completion), street bets, and chronological history. It chooses the first nonfolded opponent in seat order, falling back to seat 1 for an uncontested hero win. The chosen opponent's parameters are prefilled. Hidden opponent cards are never transferred.

Untouched imports carry their hand ID/revision and engine-supplied legal actions. Completed hands have an empty action list. Manually editing any field or range switches to a hypothetical spot and removes trusted legal actions; history text is never treated as a validated replay. Editing Study never changes the trainer session.

## Profile assumptions

All archetype values below are **illustrative configuration defaults**, not measurements, universal definitions, or promises that actual sampled action statistics equal these numbers. Percent fields use the 0–100 scale. PFR cannot exceed VPIP. Conditional statistics such as 3-bet are not incorrectly constrained to be below PFR.

| Parameter | TAG | LAG | Tight Passive | Loose Passive |
| --- | ---: | ---: | ---: | ---: |
| VPIP | 24 | 38 | 18 | 45 |
| PFR | 20 | 30 | 9 | 12 |
| 3-bet | 7 | 12 | 3 | 4 |
| Fold to 3-bet | 55 | 35 | 70 | 38 |
| Flop continuation bet | 60 | 72 | 30 | 40 |
| Fold to flop c-bet | 45 | 32 | 62 | 25 |
| Turn aggression | 45 | 70 | 22 | 28 |
| River aggression | 40 | 62 | 15 | 18 |
| Calling tendency | 45 | 62 | 45 | 85 |
| Bluffing tendency | 35 | 65 | 12 | 18 |

**Standard GTO** has no assumed percentages and is not solver-backed. Until a validated provider supports a spot, selecting it in Trainer explicitly uses the original Task 002 random heuristic fallback. The UI states that fallback.

Profile selection updates descriptions, parameters, comparison cards and the generated opponent range. Parameter edits regenerate that model range, replacing manual opponent-range edits; this behavior is explained next to the editor. Reset restores only the selected archetype's defaults. Hero range edits are independent.

## Range representation

`ranges.py` defines a 13×13 matrix in descending AKQJT98765432 order:

- Pairs on the diagonal: 13 classes with 6 combinations each.
- Suited hands above it: 78 classes with 4 combinations each.
- Offsuit hands below it: 78 classes with 12 combinations each.
- Total: 169 classes and 1,326 exact unordered two-card combinations.

A `HandRange` maps class names to integer inclusion weights from 0 to 100. All combinations within a class share that weight. Cell fill is inclusion weight, **not an action frequency or hand equity**. Clear, select-all, toggling and individual weight editing are supported.

Weighted combination counts sum class combination count × weight / 100. Known board cards block both ranges. Known hero cards additionally block the opponent range; they are not removed from the hero's hypothetical range. No hidden opponent cards are used. Counts are rounded to two decimals for display.

The initial model targets approximately VPIP% of the 1,326 combinations, using a deliberately simple ordering:

- Pair score: 3 × rank + 18.
- Other hands: 2 × high rank + low rank, plus max(0, 4 − rank gap).
- Suited bonus: 3 + bluffing tendency / 25.
- Classes fill in descending score order; the last class may have a partial integer weight.

The ordering is **not a validated hand-strength, equity, positional strategy, or opening-range calculation**. Standard GTO generates no range. Changing profile parameters never produces an equilibrium claim.

## Trainer behavior

`ProfilePolicy` implements the existing `OpponentPolicy` interface. It uses only engine-legal actions and sizing bounds, with the session's seeded random generator.

- Preflop pressure uses PFR in an unraised pot, or the 3-bet parameter when facing a raise.
- Preflop continuation combines 60% VPIP and 40% calling tendency, scaled down by fold-to-3-bet against a raise.
- Postflop pressure uses flop c-bet, turn aggression, or river aggression as appropriate.
- Postflop continuation combines 65% calling tendency and 35% (100 − fold-to-flop-c-bet).
- Raise probability is (45% pressure + 15% bluffing tendency) / 100, followed by the continuation/fold decision. Full-raise size is a pot fraction derived from pressure and clamped to the engine bounds.

These are directional heuristics. The policy does not identify real c-bet opportunities, compute card-aware bluffs, fit target population statistics, calculate equity, or choose exploitative best responses. Tests check distinct tendencies, legal behavior and reproducibility, not strategic optimality.

Omitting opponent configurations in the API preserves Task 002's random-policy behavior. An omitted configuration on a subsequent hand retains that session's previous configuration. New frontend hands submit exactly five profiles. Client-supplied cards, stacks, and pot values are still forbidden in trainer requests.

## API additions

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | /api/profiles | Five default descriptions, assumptions and availability states |
| POST | /api/study | Validate a hypothetical spot and return modeled/calculated/unavailable data |
| GET | /api/study/current | Session-owned public trainer snapshot in Study format |
| POST | /api/games | Existing endpoint; optional `opponents` array of exactly five `ProfileConfig` values |

Study endpoints use the existing same-origin proxy, JSON/Origin mutation checks and private/no-store responses. Importing requires the existing HttpOnly session cookie. A public hand ID cannot grant access to another browser's session.

## Provider architecture

`StrategyProvider.analyze(ProviderContext) -> StrategyResponse` separates three implementations:

1. `PrecomputedGTOProvider`: unavailable until a validated dataset and supported-spot lookup are supplied.
2. `StatisticalOpponentModel`: model-only assumptions and explanations; no solver probabilities, EV or equity.
3. `CustomCFRProvider`: reserved interface; no CFR algorithm is executed.

Provider context carries the complete Study spot, both ranges, resolved profile, state identifier and legal actions when trusted. Trainer imports additionally supply the public engine snapshot, including remaining stacks and legal sizing; no private opponent cards or engine deck are passed.

Responses carry the state ID, legal actions (null for unverified manual spots), optional frequencies/EV/equity, source, calculation method, assumptions, confidence, availability and explanation. The state ID hashes the request and trainer hand/revision where applicable.

Contract validators reject numeric solver outputs from unavailable/model-only responses, invalid frequency normalization, values outside legal actions, nonfinite EV, out-of-range equity and an available solution lacking validated confidence. Synthetic numeric fixtures exist only in contract tests and are not bundled strategy records. Future providers must substantiate validation with actual source/provenance and spot coverage; setting a flag is not mathematical validation.

## Verification and limitations

Run the existing Python tests, Ruff, mypy, `npm test`, `npm run typecheck`, `npm run build` and `npm run test:e2e`. The browser suite now covers default Study navigation, range edits, profile changes, board facts, mobile layout, configured trainer behavior, and current/completed hand transfer, as well as the original complete-hand gameplay tests.

The engine/evaluator and MIT LICENSE are preserved. Session storage remains in memory and requires a single backend worker, as documented for Task 002. Study edits are component-local and do not persist across reloads. No GTO dataset, equilibrium solver, hand equity engine, best-response calculation, account system, range database, or detailed hand analyzer is implemented. Docker remains unverified locally.
