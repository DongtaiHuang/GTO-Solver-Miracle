"""Run from backend after installing the project; writes measurements, not fixtures."""

import argparse
import json
import platform
import statistics
import time

from poker_lab.equity import PlayerInput, calculate_equity
from poker_lab.ranges import CLASSES


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--samples", type=int, default=2000)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 10:
        parser.error("Use one to ten repeats")
    hands = [PlayerInput(cards=("As", "Ah")), PlayerInput(cards=("Ks", "Kh"))]
    ranges = [PlayerInput(weights=dict.fromkeys(CLASSES, 100))] * 2
    cases = [
        ("river_hand_exact", hands, ("2c", "3d", "7h", "8c", "Jd"), "exact"),
        ("turn_hand_exact", hands, ("2c", "3d", "7h", "8c"), "exact"),
        ("flop_hand_exact", hands, ("2c", "3d", "7h"), "exact"),
        ("preflop_hand_mc", hands, (), "monte_carlo"),
        ("river_full_ranges_mc", ranges, ("2c", "3d", "7h", "8c", "Jd"), "monte_carlo"),
    ]
    rows = []
    for name, players, board, method in cases:
        timings = []
        for _ in range(args.repeats):
            start = time.perf_counter()
            result = calculate_equity(players, board=board, method=method, samples=args.samples)
            timings.append(time.perf_counter() - start)
        rows.append(
            {
                "case": name,
                "median_seconds": round(statistics.median(timings), 4),
                "evaluated_outcomes": result.evaluated_outcomes,
                "method": result.method,
            }
        )
    print(
        json.dumps(
            {
                "python": platform.python_version(),
                "os": platform.system(),
                "repeats": args.repeats,
                "requested_samples": args.samples,
                "benchmarks": rows,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
