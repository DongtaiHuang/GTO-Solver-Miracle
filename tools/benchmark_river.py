"""Bounded benchmark. Trace one full iteration after training for memory accounting."""

import json
import time
import tracemalloc
from pathlib import Path

import numpy as np
from river_cfr import RiverGame

raw = json.loads(Path(__file__).with_name("expanded_ranges.json").read_text())
for n in (2, 4, 8):
    ranges = [
        [((k[:2], k[2:]), w) for k, w in list(raw[seat].items())[:n]]
        for seat in ("BTN", "BB")
    ]
    start = time.perf_counter()
    game = RiverGame(ranges)
    game.train(1000)
    gap = game.report()[-1]
    elapsed = time.perf_counter() - start
    tracemalloc.start()
    measurement = RiverGame(ranges)
    measurement.train(1)
    measurement.report()
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    print(
        n,
        1000,
        round(elapsed, 3),
        peak,
        5 * n,
        np.count_nonzero(game.chance) * len(game.term),
        round(gap, 8),
    )
