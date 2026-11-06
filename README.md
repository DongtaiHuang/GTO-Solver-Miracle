# GTO-Solver-Miracle
A full-stack Texas Hold'em GTO trainer and hand history analyzer featuring opponent modeling, exploitative strategy adjustments, and poker solver algorithms.

The description above states the long-term project vision. The implementation below is limited to Task 001.

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

The frontend is a static foundation page; it does not expose private cards or provide a network gameplay API. The engine is directly usable from Python and imports no web-framework code.

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
