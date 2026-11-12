# Training Center

Open **Training Center** in the workspace navigation. Select a benchmark, street, position and exercise. Each action button submits the indicated action at its exact size. The feedback compares actions for Hero's known combination at the displayed public decision. Begin new session groups subsequent attempts separately. Retry preserves the exercise and creates a fresh attempt.

## Coverage and identity

The catalog reads reviewed, redistributable records with combo EVs from the existing strategy registry. The bundled library contains 37 public decisions: four Task 006A river decisions, five Task 008 expanded river decisions and 28 Task 009 turn/river decisions. A prompt identifies the solution, SHA-256 content hash, canonical public scenario hash and exact private combo. Its position, blind, pot, public cards, ordered history and action keys come from that record. The scenario hash incorporates the full tree abstraction and range assumptions. A linked exercise must match the source, public hash and combo. Synthetic records never enter the exercise list.

Study links an individually selected combination into practice. A calculated Task 011 response also links its explicit hypothesis, including row edits. Trainer's completed-hand review leads to Analyzer. Select a Hero decision and a compatible range/tree in Analyzer to practice the spot or explicitly save its recorded action. The review ID derives from a local digest of the hand context and decision. Equivalent manual histories can share an ID. Random hands usually lack coverage. Browsing a replay creates no attempt.

## Grading and verification

The backend resolves each submission against the catalog and grades only a positive-reach combination. All utilities are incremental chips from the acting player's perspective at the same information set. The benchmark for GTO practice is the published equilibrium-continuation action EV. The modeled benchmark uses the Task 011 response continuation against the selected fixed policy. It evaluates the bounded compiled reference without running CFR+. A zero-reach response, missing action values, mismatched source or unsupported sizing yields an ungraded response.

For chosen action a and complete action values Q, loss = max(Q) − Q[a]. Differences at most 1e-8 chips count as numerical ties. The published solver gap describes the equilibrium approximation globally; it does not provide a per-combination error bound. Frequencies describe the policy mix and never multiply the loss. Conditional response gain and equilibrium cost compare entire continuations for this combo, independently of the user's selected action. The UI reports them separately. No root-level EV enters decision grading.

### Worked exercise

Select Model · TAG, turn, BB and **ts-root-v1 · BB · KhQh**. On Kd 7h 2s Tc, the pot is 550 and the big blind is 100 chips. Select **bet@275**. Against fixed TAG with the optimized continuation, checking is worth 367.181971 chips and betting is worth 246.607795. The loss is **120.574177 chips**, or **1.205742 BB**. This same combo's conditional model gain is 70.005712 chips and equilibrium cost is 15.458638 chips. These measure changing policy.

With just this attempt the model group contains one graded observation and mean loss 1.205742 BB. GTO mean is unavailable. Retry and check to record zero loss; model mean then becomes 0.602871 BB across two attempts on one exercise. Under the separately published GTO benchmark, betting instead costs about 0.007839 chips. None of these numbers is realized hand profit.

## API and persistence

- GET /api/strategy/training/exercises returns public prompts and Hero combos.
- POST /api/strategy/training/grade accepts solution_id, scenario_id, version, combo, action and optional Task 011 hypothesis. A sized action uses the solver key, e.g. bet@275. Model presets and row semantics are documented in TASK011.md.
- POST /api/strategy/training/report validates a version-1 archive, verifies submitted feedback against its original solution and hypothesis, and returns the normalized archive and metrics. The service stores no user history. Duplicate IDs, duplicate JSON keys, unknown fields, changed sources and altered EVs fail import. Recorded timestamps, session identity and retry labels are user-supplied historical context; a local archive does not authenticate real play.

Session storage holds at most 64 attempts in 64 KiB. Each records its submission, benchmark, timestamp, session and attempt IDs, first/retry indicator, practice/review origin, position, street, frequencies, conditional action values and grade. Grade and report requests have a 64 KiB body limit and share bounded calculation capacity. Reopening checks the archive. A stale archive can still be exported; its scores are never silently updated. No historical regrading or old solver bundle archive is provided. Export before closing the tab or replacing/resetting the history. An imported file replaces this tab's archive. A duplicated browser tab may start with a copy. No cloud storage or cross-user lookup exists.

The report sums BB losses and divides by graded count separately for each benchmark, street, position, scenario, session and first/retry group. Zero-loss observations count; ungraded attempts have null loss. Empty grades have unavailable totals and means. Recent attempts, session trends and repeated loss counts describe only this small practice library. Manual history edits cannot prove performance. Hidden opponents and future runouts are never sampled or revealed by practice.

Random selection maps a 32-bit seed through one LCG step (1664525 × seed + 1013904223 modulo 2^32) into the ordered, filtered catalog. Interactive seeds use browser randomness. Missed practice selects among exact exercises with positive measured loss under the same policy. Highest-loss focus chooses the largest previously observed loss within the filters. These are selection rules, not estimates of poker ability.

## Reproduction

Install the dependencies from README, including the numerical test dependencies from TASK009.md. Run pytest, ruff check . and mypy from backend. At repository root run python -m pytest -q tools, npm test, npm run typecheck, npm run build and npm run test:e2e. The backend training tests reproduce the worked decision and verify import rejection, retries and numerical ties. The mobile browser test exercises the actual API, tab storage, keyboard submission and JSON import.
