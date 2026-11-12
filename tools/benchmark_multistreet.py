"""Time complete three-model comparisons including catalog matching, outside HTTP."""

import statistics
import time
import tracemalloc

from poker_lab import multistreet as ms
from poker_lab.strategy_catalog import configured_catalog

catalog = configured_catalog(None)
ctx = catalog.source("ts-root-v1", "validated_gto")
s = ctx.document.scenario
base = {
    "reference_version": ms.VERSION,
    "scenario": s,
    "solution_id": ctx.document.solution_id,
    "opponent": "BTN",
}
rows = ms.policy_rows(ms.Context.model_validate(base), catalog)
edits = []
for key, hands in rows.items():
    for combo, probs in hands.items():
        if len(edits) < 32:
            a, b = probs
            edits.append(
                {"node": key, "combo": combo, "probabilities": {a: 0.3, b: 0.7}}
            )
req = ms.Request.model_validate(
    {
        **base,
        "hypotheses": [
            {"name": str(r), "profile": "tag", "opening_bet": r, "overrides": edits}
            for r in (0.25, 0.4, 0.55)
        ],
    }
)
samples = []
for _ in range(5):
    start = time.perf_counter()
    ms.analyze(req, catalog)
    samples.append(time.perf_counter() - start)
ms.reference.cache_clear()
tracemalloc.start()
ms.analyze(req, catalog)
print(
    "Seconds median/max",
    statistics.median(samples),
    max(samples),
    "cold traced peak bytes",
    tracemalloc.get_traced_memory()[1],
)
tracemalloc.stop()
req = ms.Request.model_validate(
    {**base, "hypotheses": [{"name": "TAG", "profile": "tag"}]}
)
result = ms.analyze(req, catalog).results[0]
print(result.root.model_dump(), result.decisions[0].model_dump())
