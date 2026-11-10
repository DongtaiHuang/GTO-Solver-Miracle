# GTO-Solver-Miracle
A full-stack Texas Hold'em GTO trainer and hand history analyzer featuring opponent modeling, exploitative strategy adjustments, and poker solver algorithms.

The description above states the long-term project vision. The current implementation includes the Task 001 engine, Task 002 interactive trainer, Task 003 strategy dashboard, Task 004 equity engine, and Task 005 exact strategy integration.

---

## Task 006B — Opponent-specific river responses

Query a supported river decision in Study to compare equilibrium play and a best response to editable opponent combo probabilities. [Assumptions, EV formulas and reproduction](docs/TASK006B.md).

## Task 006A — Solver-generated river strategies

Study includes four reviewed decisions from two bounded BTN versus BB river games. Select a river scenario and query it to inspect individual combinations, mixed actions, chip EV and measured equilibrium error. [Solver, ranges, accuracy and reproduction](docs/TASK006A.md).

## Task 005 — Exact strategy integration

Study now opens in **Strategy visualization**, with exact scenario lookup, a mixed-frequency 169-hand matrix, combination details, sized actions, postflop history, provenance, and a side-by-side opponent-assumption comparison. **Range editing & equity** preserves the existing editable ranges and equity tools; Trainer remains at /trainer.

At the Task 005 milestone the default GTO catalog was empty and displays **GTO solution unavailable**. Four synthetic preflop/flop/turn/river examples require an explicit opt-in and are never presented as GTO recommendations. Real exports require explicit source/redistribution permission and trusted, content-bound local review; metadata alone does not prove mathematical correctness. No exploitative best response is calculated.

See [Task 005 dataset format, local import, review requirements, and limitations](docs/TASK005.md). Administrative import is a local CLI only. Keep private inputs/catalogs outside Git and Docker images, for example under the ignored .strategy-data/ directory. Existing development and validation commands below still apply.

---

## Task 004 — Real showdown equity

Study now calculates specific hand vs hand, hand vs weighted range, and range vs range equity using the existing evaluator. The backend additionally supports 2–6 players with fractional tied-pot shares. Small cases enumerate exactly; larger cases use bounded, seeded Monte Carlo with reported valid sample counts, standard errors, and conservative 95% intervals.

In Equity Analysis, explicitly edit or adopt an assumed opponent range, choose cards/ranges/board/dead cards and method, then click **Calculate equity**. Nothing expensive runs on every keystroke. Pot odds use the calculated equity and a user-specified call amount, with the single-pot/no-future-betting assumptions clearly displayed. GTO frequencies and solver action EV remain unavailable.

See [Task 004 algorithms, probability assumptions, limits, and benchmarks](docs/TASK004.md). The same development and validation commands below apply, including all existing tests and real browser flows. No new runtime dependency or alternate hand evaluator was introduced.

---

## Task 003 — Strategy dashboard and opponent modeling

Study is now the default landing page at http://localhost:3000. The playable table is preserved at http://localhost:3000/trainer, with a reserved Hand Analyzer at /hand-analyzer.

Study includes the 169-class range matrix, independent hero/opponent inclusion weights, configurable full-hand context, five opponent profiles, exact combo/blocker and board facts, and explicit availability panels. **GTO solution unavailable** means no validated strategy data exists; no GTO frequencies, EV, equity, or exploitative recommendations are invented. Standard GTO is not yet solver-backed.

Before a trainer hand, configure each of the five opponents. TAG, LAG, Tight Passive, and Loose Passive use distinct seeded heuristics. Standard GTO explicitly falls back to the original random heuristic. Current or completed trainer hands can open in Study using only the session-owned public state.

See [Task 003 architecture and assumptions](docs/TASK003.md) for parameter defaults, range and policy formulas, API/provider contracts, data boundaries, and limitations. This branch is based on Task 002 commit 9cd1fea and depends on that implementation.

Development commands below remain valid. Run the complete Python and frontend suites, including `npm run test:e2e`, as described in the Task 003 document.

---

## Task 002 — Interactive Poker Trainer

The trainer now plays complete six-player hands against five automated opponents. Hero occupies seat 0; the button rotates between hands. Each new practice hand resets all stacks to 10,000 integer chips (100 BB). This is a basic heuristic training table, not a solver or a GTO strategy recommendation.

### Start the trainer

From the repository root, install backend dependencies as shown below, then run:

```powershell
.\.venv\Scripts\python.exe -m uvicorn poker_lab.api:app --host 127.0.0.1 --port 8000 --reload
```

In a second terminal:

```sh
npm ci
npm run dev
```

Open http://localhost:3000/trainer and choose **New Hand**. A browser reload restores the active hand. Opponents automatically act until the next hero decision; folding or going all-in runs the remaining hand to settlement. New Hand is available after completion. Opponent cards stay hidden on the server until a contested showdown; folded opponent cards and all opponent cards in uncontested hands remain hidden.

The table displays positions, stacks, committed street bets, status, board, total pot, effective stacks, chronological history, and per-pot payouts. Effective stack is the smaller of hero's remaining stack and the largest remaining nonfolded opponent stack; each player's public view also includes their effective stack against hero.

Bet and raise inputs are **total street contributions**, not increments. Server-provided presets use the selected fraction of the pot after calling, added to the current wager, then clamp to the engine's legal full-raise range. Short all-ins use the All-in action; they are never disguised as a legal full raise. A short raise that has not reopened betting removes the raise controls.

### API and ownership

| Method | Path | Request |
| --- | --- | --- |
| POST | /api/games | `{}` — start a session or the next completed hand |
| GET | /api/game | Restore the current session's public state |
| POST | /api/game/actions | `{"hand_id":"…","revision":0,"action":"raise","amount":300}` |

The Next.js server proxies only these routes to FastAPI. No direct cross-origin browser API calls or browser-readable session tokens are needed. Every response is marked private and noncacheable.

Sessions use an opaque, cryptographically random HttpOnly, SameSite=Strict cookie scoped to /api. The backend selects seeds using server entropy; clients cannot supply or retrieve seeds, decks, stacks, or pot values. Tests can inject fixed seeds internally. A hand ID identifies a hand but never grants access to it. Each operation requires the owning session cookie. Action payloads reject unknown fields and noninteger amounts, then pass through the original engine's validation.

Hand IDs and revision numbers reject stale or duplicate decisions. The server locks session operations and commits the hero decision and subsequent bot actions together. The client disables controls during requests and refreshes authoritative state after a failed response before allowing further decisions.

Error responses: 400 for illegal engine actions, 404 for missing/expired sessions, 409 for stale or completed-hand actions or replacing an unfinished hand, 422 for invalid payloads, 503 when session capacity is reached. Mutation requests require JSON and reject an unapproved Origin.

### Configuration and Docker

| Variable | Service | Default |
| --- | --- | --- |
| BACKEND_URL | Next.js server | http://127.0.0.1:8000 |
| TRAINER_ORIGIN | FastAPI | http://localhost:3000 |
| COOKIE_SECURE | FastAPI | false; set true when using HTTPS |

Set these as process environment variables when changing hosts or using HTTPS. Docker Compose connects the frontend to http://backend:8000 automatically and serves the UI at http://localhost:3000. Docker execution has not been verified locally because Docker is unavailable in this environment.

### Tests

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest
..\.venv\Scripts\python.exe -m ruff check .
..\.venv\Scripts\python.exe -m mypy
cd ..
npm test
npm run typecheck
npm run build
```

For real browser tests, install Chromium once, set PYTHON to the virtual environment's Python executable, and run:

```powershell
$env:PYTHON = (Resolve-Path .\.venv\Scripts\python.exe).Path
$env:PLAYWRIGHT_BROWSERS_PATH = "$PWD\.playwright-browsers"
cd frontend
npx playwright install chromium
cd ..
npm run test:e2e
```

On macOS/Linux use .venv/bin/python. Browser tests start the production frontend and backend, play through settlement, start another hand, verify hidden cards, and check the mobile viewport. Run the production build before them. CI runs Python checks, component tests, frontend checks/build, browser tests, and Docker smoke checks.

### Current limitations

- Sessions are process-local memory, expire after two hours of inactivity, and are capped at 512. Restarting the backend loses hands. Run a single backend worker; shared storage and account authentication are future work. The browser cookie expires two hours after a new hand is created.
- Different browser profiles have isolated sessions. Tabs in the same browser share a session and stale decisions are rejected.
- The policy is a seeded randomized heuristic over legal actions. It has no strategic optimality guarantees and no equity, GTO, exploitative modeling, or coaching claims. Replace the `OpponentPolicy` protocol implementation for later models.
- Bot actions run synchronously before each response; there is no paced animation, live multiplayer, or tournament bankroll persistence.
- The suite currently reports a non-failing upstream Starlette warning about its httpx test-client integration.

Task 001's independent engine, integer chip accounting, evaluator, tests, and MIT license remain intact. The original foundation documentation follows for reference.

---

# Poker Strategy Lab — Task 001

A Next.js / TypeScript frontend and FastAPI / Python backend monorepo with an independent, deterministic No-Limit Texas Hold’em rules engine. No solver, GTO ranges, equity simulation, training workflow, persistence, authentication, or strategy recommendations are implemented.

## Layout

```text
frontend/app/                 Next.js App Router project shell
backend/src/poker_lab/
  models.py                   Typed players, actions, streets, pots and awards
  engine.py                   Single-hand state machine, betting and settlement
  evaluator.py                Exact best-five-of-seven hand ranking
  api.py                      FastAPI health endpoint only
backend/tests/                Rule examples, evaluator cases and seeded simulations
.github/workflows/ci.yml      Python checks, frontend build, Docker smoke checks
compose.yaml                 Local frontend and backend services
```

## Run locally

Requires Python 3.12+ and Node.js 24 (Node 20.9+ is the framework minimum).

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e './backend[dev]'
.\.venv\Scripts\python.exe -m uvicorn poker_lab.api:app --reload
```

In a second terminal at the repository root:

```sh
npm ci
npm run dev
```

Frontend: http://localhost:3000. Backend health: http://localhost:8000/health. API documentation: http://localhost:8000/docs. On macOS/Linux, substitute `.venv/bin/python` for `.\.venv\Scripts\python.exe`.

At the Task 001 milestone, the frontend was a static foundation page with no network gameplay API; Task 002 adds the trainer described above. The engine is directly usable from Python and imports no web-framework code.

## Engine contract

```python
from poker_lab.engine import Holdem
from poker_lab.models import Action

game = Holdem(seed=42)  # six seats; button at seat 0
assert game.actor == 3
assert game.legal_actions().min_raise_to == 200
game.act(3, Action.RAISE, 300)  # total street contribution, not +300
game.act(4, Action.CALL)
```

- Defaults: six occupied seats, 10,000 chips each (100 BB), small blind 50 and big blind 100. All chip amounts are integers. No rake or antes.
- Seats run clockwise from zero. The button, optional 2–6 occupied seats, even big-blind size, and positive custom stacks are configurable for testing and future callers. Sitting out and zero-stack seats must be removed by the caller before a new hand.
- A seeded private `random.Random` produces a reproducible shuffle without changing global RNG state. Alternatively, supply a complete permutation of the 52 card strings (`2c` through `As`). Cards are consumed from the front. Seeded randomness is for experiments, not secure real-money dealing.
- Deal two rounds starting left of the button; in heads-up the button posts the small blind and acts first preflop. Burn one card before flop, turn and river. First postflop action is left of the button.
- `legal_actions()` describes only the current actor: available actions, actual capped call cost, minimum full raise-to (or `None`), and total available street contribution. `act()` rejects out-of-turn actions, fractional amounts, under-raises, over-stack raises, and amounts on non-bet actions before changing state.
- `BET` opens an unbet street; `RAISE` increases a bet. Both require a full minimum raise. `ALL_IN` handles short raises and short calls. Minimum raises use the last full increment, starting at one BB per street.
- A short all-in does not itself reopen betting for a player who already acted. Cumulative short raises reopen betting once that player faces at least a full raise. Players who have not acted retain raise rights. A sole player with chips may call or fold but cannot bet into all-in opponents.
- Betting closes when all nonfolded players with chips have acted and matched the wager. All-in hands run out automatically once no further decisions remain. A fold win settles immediately without revealing a board.
- Contributions include folded money. Side pots are built at distinct contribution levels; only nonfolded contributors at that level can win. A one-contributor top tier returns the unmatched excess. Ties split evenly; odd chips go clockwise starting left of the button, independently for each pot.
- Seven-card evaluation enumerates all 21 five-card subsets, including ace-low straights. Rank tuples compare lexicographically, from high card `(0, ...)` to straight flush `(8, high_card)`. Suits never break ties.
- At completion, `awards` retains each pot's amount, eligible seats, winners and payouts. Award records include unmatched excess. Contributions and street bets reset to zero; stacks contain all settled chips. `actor` is `None`, legal actions are empty, and further actions are rejected.
- A `Holdem` instance represents one hand. Construct the next instance with the desired button and stacks. Public dataclasses support inspection; callers must treat engine state as read-only and submit changes through `act()`.

## Verification

From `backend`, after installing development dependencies:

```powershell
..\.venv\Scripts\python.exe -m pytest
..\.venv\Scripts\python.exe -m ruff check .
..\.venv\Scripts\python.exe -m mypy
```

From the root:

```sh
npm run typecheck
npm run build
```

Pytest enforces at least 95% combined statement and branch coverage. Tests cover deterministic dealing, positions and blind options, legal and rejected actions, full and short raises, cumulative reopening, all-in runouts, folded contributions, multiple side pots, unmatched excess, split pots and odd chips, all hand categories and kickers, and 150 seeded legal-action simulations with chip-conservation and termination assertions. These are software correctness checks, not a claim of strategic optimality or a formal proof of all game sequences.

## Docker

```sh
docker compose up --build --wait
docker compose down
```

Both application containers run as non-root users. GitHub Actions runs Python lint/type/test checks, a TypeScript check and production frontend build, then builds and smoke-tests both containers. The npm lockfile pins the frontend installation. Python dependency ranges and optional development tooling are declared in `backend/pyproject.toml`.

Framework setup reference: [Next.js installation documentation](https://nextjs.org/docs/app/getting-started/installation).
