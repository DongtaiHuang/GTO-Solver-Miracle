# Task 006A — BTN versus BB river solutions

Study ships four public decision records. Choose **river-550-btn-v1** under Supported exact scenario and query it. Select **54s** to inspect the bluff combo. The BB record is the response after a bet. The 275-chip tree has its own pair of records and distinct scenario identifiers.

## Solver selection

[TexasSolver](https://github.com/bupticybee/TexasSolver) supports configurable postflop trees and console strategy dumps. Its README reports about 1.6 GB for one flop benchmark and discusses commercial licensing and release-package distribution separately from its AGPL source. [postflop-solver](https://github.com/b-inary/postflop-solver) provides a Rust heads-up postflop library, configurable action trees, per-hand strategy and expected-value access, and exploitability measurement. Its AGPL source and suspended development are relevant to distributing a linked application. Neither benchmark throughput nor solver accuracy transfers across different trees and ranges.

For this library we selected **HiGHS 1.8.0 dual simplex**, via **SciPy 1.15.3**, with an original MIT-licensed fixed-river Hold'em adapter in tools/solve_river.py. HiGHS consumes numerical linear constraints. The adapter constructs the poker payoff matrix, solves both players' maximin programs, converts mixed pure policies to combo probabilities, computes incremental action EV and writes Task 005 records. The choice makes the entire restricted game small enough to independently enumerate every unilateral deviation. HiGHS uses the MIT license and SciPy uses BSD-3-Clause. Generation is offline. The application redistributes original project-produced numerical records under the repository MIT license. [HiGHS source and license](https://github.com/ERGO-Code/HiGHS) · [SciPy solver interface](https://docs.scipy.org/doc/scipy-1.15.3/reference/optimize.linprog-highs-ds.html)

## Tree and units

Six 10,000-chip stacks, 50/100 blinds, zero rake and ante. UTG, HJ and CO fold. BTN raises to 250, SB folds, BB calls 150. The 550-chip pot includes the dead small blind. Both players have 9,750 behind. BTN's explicit conditional opening range is AcAd or 5c4c, equally weighted. BB's defending range is KhQh or KsJs, equally weighted. These are study inputs, with no claim about optimal preflop play.

The fixed flop is Kd 7h 2s, turn Tc, river 9d. Flop and turn are conditioned on check-through, and BB checks river. The library solves two distinct abstractions. BTN can check or bet either 275 in one tree or 550 in the other. Facing that tree's bet BB may fold or call. Checking dominates folding when BTN faces no wager, so a zero-frequency fold extends the policy to the engine's legal fold action. All four private-card deals are compatible and have probability 1/4. No future cards remain. Earlier-street betting, raises, alternate runouts, ranges and unrestricted sizing fall outside this library.

## Accuracy and EV

Four pure policies per player produce a 4 × 4 payoff matrix (128 bytes of double-precision coefficients before optimizer overhead). Normal-form size grows exponentially with private information sets. This implementation targets the two fixed two-combo ranges. The existing evaluator ranks each showdown. BTN receives its final pot share minus river investment. BB receives the remaining constant-sum payoff. BB call EV conditions on observing BTN's bet. The two BB hands can be strategically interchangeable, so individual optimal mixes need not be unique.

For returned distributions x and y and BTN payoff matrix A, the full best-response gap is max(Ay) minus min(xA). Generation enforces a 1e-8-chip tolerance. Measured gaps were 0 chips at 550 and 5.68434188608e-14 chips at 275. These are floating-point measurements for this tree. In the pot-size tree the bluff bets with probability 1/2 and the aggregate BB calls with probability 1/2. The dashboard reports the measured gap in Coverage & provenance.

## Reproduce and import

From the repository root with Python 3.12 and the backend installed, install the offline generation dependencies in the virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install scipy==1.15.3 numpy==2.4.6
.\.venv\Scripts\python.exe tools/solve_river.py --bet 550 --verify
.\.venv\Scripts\python.exe tools/solve_river.py --bet 275 --verify
```

Verification re-solves the game, reconstructs both records, and compares all values and approval hashes with the packaged JSON using its original timestamp. Omitting --verify regenerates the selected artifact with a fresh UTC timestamp. Each file contains Task 005 ImportedSolution records carrying scenario, exact action mapping, per-combo rows, source, methodology, limitations, and hash-bound approval. The backend validates each envelope on startup and exposes it through the exact strategy query. Optional private catalogs still undergo the Task 005 import and publication checks.

To export a standard dataset for a separate catalog, wrap the document field from each entry in a Dataset. For example, from PowerShell:

```powershell
$records = Get-Content backend/src/poker_lab/data/river_550.json -Raw | ConvertFrom-Json
@{schema_version="1.0";dataset_id="river-550-v1";solutions=@($records.document)} | ConvertTo-Json -Depth 50 | Set-Content -Encoding utf8NoBOM river-export.json
.\.venv\Scripts\python.exe -m poker_lab.strategy_import river-export.json --catalog .strategy-data/review.db
```

The separate catalog is for inspection. Loading duplicate IDs alongside the bundled records fails. Additional permitted exports use the review and import workflow in [Task 005](TASK005.md).
