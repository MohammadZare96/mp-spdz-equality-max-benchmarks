#!/usr/bin/env python3
"""Aggregate raw benchmark runs into publication-friendly CSV files."""

from __future__ import annotations

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path


GROUP_FIELDS = ("sweep", "operation", "L", "K", "N", "protocol", "prime")


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw", type=Path)
    parser.add_argument("summary", type=Path)
    args = parser.parse_args()

    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    with args.raw.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["correct"].lower() != "true":
                raise ValueError("raw CSV contains an incorrect run")
            grouped[tuple(row[field] for field in GROUP_FIELDS)].append(row)

    output_fields = list(GROUP_FIELDS) + [
        "runs",
        "runtime_median_seconds",
        "runtime_p25_seconds",
        "runtime_p75_seconds",
        "communication_median_mb",
        "communication_p25_mb",
        "communication_p75_mb",
    ]
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    with args.summary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_fields)
        writer.writeheader()
        for key, rows in sorted(grouped.items()):
            runtimes = [float(row["runtime_seconds"]) for row in rows]
            communications = [float(row["global_communication_mb"]) for row in rows]
            writer.writerow(
                dict(
                    zip(GROUP_FIELDS, key),
                    runs=len(rows),
                    runtime_median_seconds=statistics.median(runtimes),
                    runtime_p25_seconds=percentile(runtimes, 0.25),
                    runtime_p75_seconds=percentile(runtimes, 0.75),
                    communication_median_mb=statistics.median(communications),
                    communication_p25_mb=percentile(communications, 0.25),
                    communication_p75_mb=percentile(communications, 0.75),
                )
            )


if __name__ == "__main__":
    main()
