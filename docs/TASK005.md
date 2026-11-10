# Task 005 — Exact strategy datasets and visualization

Study opens in **Strategy visualization**. The existing **Range editing & equity** workspace and Trainer remain available. The poker rules, evaluator, equity algorithms, session ownership, and opponent policies are reused.

## Coverage and what the product claims

**No genuine solver dataset is included.** The default public catalog has zero approved GTO scenarios. Unsupported situations return **GTO solution unavailable**, with null frequencies/EV and no recommendations.

Four MIT-licensed, original **synthetic UI fixtures** cover one preflop, flop, turn, and river node. Users must select **Show synthetic examples (UI only, not GTO)**, choose an example, and query it. Every fixture view, comparison, and source panel identifies the data as synthetic. These toy distributions have no strategic validity and no action EV. They cannot be approved as GTO records. The fixtures live in `backend/src/poker_lab/data/strategy_demo_v1.json` and are packaged with the backend; the frontend test copy is also explicitly synthetic.

A permitted genuine export requires trusted human review before public use. Structural validation and the existence of provenance metadata **do not independently establish equilibrium, solver convergence, accuracy, or legal rights**. Approval is an administrative attestation bound to the document hash, not a cryptographic proof that poker was solved.

## Versioned export format

Both the envelope and each document/scenario require `schema_version: "1.0"`. Unknown fields are rejected. The envelope is:

```json
{
  "schema_version": "1.0",
  "dataset_id": "permitted-export-v1",
  "solutions": ["Replace this illustrative string with complete StrategySolution objects"]
}
```

That envelope illustration is not importable; the complete, importable four-solution synthetic file is the format example. For machine-readable JSON Schema, run from an installed backend environment:

```powershell
.\.venv\Scripts\python.exe -c "import json; from poker_lab.strategy_models import Dataset; print(json.dumps(Dataset.model_json_schema(), indent=2))"
```

The typed contract is in `strategy_models.py`:

| Object | Required information |
| --- | --- |
| Dataset | Version, unique dataset ID, 1–128 solutions |
| StrategySolution | Unique solution ID; kind; complete scenario; solver identifier/version; timezone-aware export time; provenance; validation; 1–1,326 combo rows |
| Scenario | Game format, all six starting stacks, small/big blinds, ante, hero/opponent positions, current effective stack and pot, street/board/dead cards, complete ordered betting history, exact sized actions, abstraction |
| Abstraction | Tree ID, range-model ID, exact-card model, no-rake model, action semantics, documented assumptions |
| Provenance | Source name and HTTPS URL, license name and HTTPS URL, explicit usage grant and evidence, redistribution permission, explicit public-publishing flag |
| Validation | synthetic_only / unverified / reviewed_gto; aware check time; methodology and evidence reference; limitations; explicit EV-verification flag |
| Combo | Two card strings, positive reach weight, frequency map, optional validated action-EV map |

Identifiers use 3–80 ASCII letters, numbers, dots, underscores, or hyphens. Card strings use the existing evaluator's exact notation, such as `As`, `Kd`, `Tc`. Chip amounts are strict integers; fractions, booleans, negative values, duplicate cards, and unknown fields are rejected.

### Scenario semantics and canonicalization

Version 1 supports six occupied NLHE cash seats, a small blind equal to half the big blind, zero ante, and no rake. It can represent six-seat hands that become heads-up after folds. Starting stacks may differ; every seat must begin with positive chips. The demo uses 10,000 chips / 100 BB. Current effective stack means the minimum of hero's and the designated live opponent's **remaining stacks**, not their starting stacks or stack-plus-bet. All six starting stacks and the full action history remain part of the key.

The scenario replays all actions through the existing independent Holdem engine, from the initial blind postings. Each history event contains its street, acting position, action, and exact amount. It must reach a live decision belonging to the hero; the designated opponent cannot have folded. Street, pot, effective stack, action order, action availability, minimum raises, and stack bounds must agree with replay.

- Fold/check use `amount: null`.
- Call uses the actual capped **incremental call cost**.
- Bet/raise use the **total street contribution**, not the raise increment.
- All-in uses the total street contribution after committing the remaining stack.
- The abstraction retains fold and the legal passive action. Multiple aggressive sizes are allowed up to the limit, with their exact integer targets.
- Duplicate keys and equivalent action aliases (such as raise-to-stack and all-in to the same target) are rejected.

Action keys are deterministic, for example `fold`, `check`, `call@100`, `raise@300`, and `all_in@10000`. Every combo must contain a frequency for every action key, including zero frequencies. Values must be finite, between zero and one, and sum to one within 1e-6. Invalid sums are rejected rather than silently normalized. EV values are finite chip values keyed by legal actions; optional partial EV maps are permitted only for reviewed, EV-verified solver exports.

Canonical JSON includes **every scenario field**. Object keys, action definitions, dead cards, and abstraction assumptions are sorted deterministically. The three flop cards are order-independent; turn and river identities and the complete history order are preserved. SHA-256 of compact, sorted canonical JSON is the scenario identifier. There is no board isomorphism, nearest-size fallback, history truncation, position substitution, stack rounding, or equity-to-strategy conversion. Range-model/tree identifiers and assumptions must also match.

Known dead cards are blockers. Each combination must be unique regardless of its two-card order, and cannot overlap the board/dead cards. Hero's candidate hole cards belong to the combo rows rather than the scenario, allowing a matrix for the whole acting range.

### Aggregation

Reach weight is a positive mass in (0, 1] supplied by the dataset for each represented combination. It is **not** an action probability or the editable class inclusion percentage. Zero-reach hands should be omitted.

Class and whole-range frequency summaries use:

```text
summary(action) = sum(reach_weight(combo) * frequency(combo, action))
                  / sum(reach_weight(combo))
```

Only represented, unblocked combinations enter those sums. Coverage reports both represented combos and all combinatorially possible unblocked combos. Missing combinations stay blank; they are never interpreted as folds. A selected combo shows its own frequencies and weight. An action's aggregate EV appears only when every represented combo has a validated value for that action, using the same reach weights.

## Trusted local import and source review

There is **no public upload/import/approval endpoint**. Only trusted administrators with local filesystem/process access should run the importer. Obtain a legally usable solver export and permission before importing it. Do not scrape proprietary services or copy their datasets.

Store private inputs and catalogs outside the repository or under the ignored `.strategy-data/` directory. This path is excluded from Git and both Docker build contexts. Do not commit confidential exports, local review evidence, credentials, or private catalogs.

Run from the repository root, after installing the backend:

```powershell
.\.venv\Scripts\python.exe -m poker_lab.strategy_import .strategy-data/permitted-export.json --catalog .strategy-data/catalog.db
```

This validates and stores a **candidate**. Metadata saying `reviewed_gto` alone cannot publish it. Check the solver's identity/version, game tree, abstraction, solving methodology, convergence/error evidence, combo mapping, units, and any EV evidence against the genuine source. Independently confirm usage and public redistribution rights. The application cannot authenticate a license statement or reproduce the solver's equilibrium proof.

After that review, import the reviewed export into a **new catalog** with explicit approval:

```powershell
.\.venv\Scripts\python.exe -m poker_lab.strategy_import .strategy-data/permitted-export.json --catalog .strategy-data/reviewed.db --approve-gto --reviewer "Responsible reviewer" --review-evidence "Reference to actual review and permission evidence" --confirm-source-and-rights
```

Approval requires all three review flags. Synthetic fixtures cannot be approved. The export must be a solver_solution with reviewed_gto validation. The approval records the exact document hash, reviewer, evidence reference, and actual server timestamp. A changed document invalidates approval. Never use fabricated metadata to promote fixtures.

A public baseline additionally requires `usage_granted: true`, `redistribution: "permitted"`, and `publish: true`. Private/unreviewed documents are absent from public queries, source metadata, and scenario listings. Local reviewer identities, approval hashes, and private evidence references are not returned through the API. Publishable source/methodology/limitation fields must themselves contain only information approved for disclosure.

SQLite imports are transactional: duplicate solution IDs or conflicting same-kind scenario definitions reject the transaction. There is no silent replacement or update. To review/replace an existing candidate, build a new catalog from the reviewed inputs and change the configured path; do not edit catalog JSON manually. An imported dataset may contain at most 124 records, reserving four of the runtime 128-record limit for packaged demos. Files are capped at 8 MiB. Duplicate JSON keys, NaN, and Infinity are rejected.

Configure the backend before starting it:

```powershell
$env:STRATEGY_CATALOG = "$PWD\.strategy-data\reviewed.db"
.\.venv\Scripts\python.exe -m uvicorn poker_lab.api:app --host 127.0.0.1 --port 8000
```

The catalog is read-only at application startup; restart after changing it. An invalid configured catalog fails startup instead of silently accepting data. Without STRATEGY_CATALOG, only synthetic examples are loaded. For containers, mount a permitted catalog read-only and explicitly set STRATEGY_CATALOG inside the container; private data is never copied into an image automatically. No dataset downloads or new runtime dependencies are introduced.

## Provider and HTTP contracts

`PrecomputedStrategyProvider`, canonical scenario models, importer, catalog, and aggregation do not depend on FastAPI or React. Existing precomputed/statistical/future-CFR interfaces remain available; the old scalar Study response cannot represent multiple exact raise sizes and remains explicitly unavailable. Free-form equity/range notes are never treated as an exact solver query.

| Method | Endpoint | Behavior |
| --- | --- | --- |
| GET | /api/strategy/scenarios | Only public, approved solver scenarios |
| GET | /api/strategy/examples | Explicitly synthetic scenario catalog |
| POST | /api/strategy/query | Complete scenario + mode; exact match, combos/classes/frequencies/optional EV/source |
| POST | /api/strategy/frequencies | Same typed exact-query contract |
| POST | /api/strategy/source | solution_id + mode; public metadata only, otherwise 404 |

Query mode defaults to `validated_gto`. Only explicit `synthetic_demo` queries can return examples, with status synthetic_demo and is_gto_recommendation false. There is no cross-mode fallback. Missing real coverage returns status unavailable, not made-up frequencies. Invalid schemas/history/actions return 422; oversized strategy POST bodies return 413 (2 MiB limit). Unknown JSON keys and duplicate JSON keys are rejected. The existing Next.js route allowlist proxies only these public reads/queries, not administrative import. Existing origin and no-store protections remain in effect.

## Study experience

1. Open Study at http://localhost:3000. The default matrix shows unavailable cells until an approved exact solution exists.
2. Choose a supported complete scenario, or expand **Complete scenario configuration (JSON)** and provide one. Query explicitly. Editing inputs clears stale results; in-flight responses cannot repopulate a different scenario.
3. Click a hand class to inspect its mixed action segments, valid-combo coverage, class-weighted probabilities, and individual combinations. Exact action sizes, board, history, assumptions, and provenance are shown alongside it.
4. Use **Show synthetic examples** only to explore the demonstration UI. Switching it off clears all example results.
5. Change any of the five opponent profiles, edit parameters, or reset defaults. The right comparison column shows **modeled assumptions**, not fabricated node action frequencies. The left column independently retains the matched solver distribution or unavailable status.
6. Use **Range editing & equity** for the existing editable hero/opponent ranges and explicit equity calculation. Trainer snapshots still open that workspace with public hand context. Trainer gameplay and hidden-card boundaries are preserved.

Equity is a showdown outcome probability under specified ranges and runouts. GTO action frequencies require a solved strategy tree and its assumptions. Simplified call EV uses the Task 004 single-pot/no-future-betting formula and is not solver EV. Opponent tendencies are configurable heuristics. A difference between them and a baseline is **not a computed exploit**; no exploitative best response, profit estimate, or new optimal frequencies have been calculated.

## Validation and limitations

Run the existing complete validation commands in README: pytest (branch coverage enabled), Ruff, mypy, npm test, TypeScript, production build, and Chromium browser tests. The new tests cover canonicalization, replay and sized actions, dataset integrity/normalization/blockers, weighted aggregation, exact misses, source rights/approval/privacy, transactional import/CLI, synthetic labeling, matrix/combo interactions, opponent comparison, stale queries, postflop views, and mobile layout. All prior trainer/equity tests remain active.

The catalog is a bounded local snapshot, not a scalable remote dataset service. Version 1 has no antes, rake, tournaments, heads-up initial seating, card-isomorphic lookup, automatic solver adapters, or solving. Full complete-history input is required. No real solver export, independent equilibrium verification, opponent best response, or exploitative EV is bundled. Docker execution remains unverified locally. The existing upstream Starlette/httpx test-client deprecation warning is non-failing.

Local Task 005 validation passed: **261 Python tests** with **99.90% combined statement/branch coverage**, **47 frontend tests**, **10 Chromium browser tests**, Ruff (including format check), mypy, TypeScript, and the production build. Docker was not run locally.
