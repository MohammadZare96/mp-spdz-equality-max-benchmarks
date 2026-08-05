#!/usr/bin/env python3
"""Benchmark plaintext and paper-SCI medians for ten gradient vectors."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.extension_common import append_csv
from benchmarks.secure_median import (
    distinct_random_matrix,
    run_secure_median,
    upper_median,
)


DEFAULT_DIMENSIONS = (100, 1_000, 10_000)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mp-spdz", required=True, type=Path)
    parser.add_argument("--dimensions", nargs="+", type=int, default=DEFAULT_DIMENSIONS)
    parser.add_argument("--clients", type=int, default=10)
    parser.add_argument("--parties", type=int, default=10)
    parser.add_argument("--L", type=int, default=16)
    parser.add_argument("--protocol", choices=("semi", "shamir"), default="shamir")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--baseline-loops", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260805)
    parser.add_argument("--timeout", type=int, default=7200)
    parser.add_argument("--output", type=Path, default=Path("results/median-vector-raw.csv"))
    args = parser.parse_args()
    if args.clients % 2 or args.clients < 2:
        raise SystemExit("--clients must be an even integer >= 2")
    if min(args.dimensions) < 1 or args.repetitions < 1 or args.baseline_loops < 1:
        raise SystemExit("dimensions, repetitions, and baseline loops must be positive")

    for dimension in args.dimensions:
        for repetition in range(args.repetitions):
            seed = args.seed ^ (dimension << 8) ^ repetition
            values = distinct_random_matrix(
                clients=args.clients,
                dimension=dimension,
                L=args.L,
                seed=seed,
            )
            started = time.perf_counter()
            for _ in range(args.baseline_loops):
                expected = upper_median(values)
            baseline_seconds = (time.perf_counter() - started) / args.baseline_loops

            secure = run_secure_median(
                values,
                mp_spdz=args.mp_spdz.resolve(),
                L=args.L,
                parties=args.parties,
                protocol=args.protocol,
                batch_size=args.batch_size,
                timeout=args.timeout,
                seed=seed,
                compile_source=(repetition == 0),
            )
            if not secure.correct:
                raise RuntimeError(f"incorrect secure median for D={dimension}")
            row = {
                "dimension": dimension,
                "clients": args.clients,
                "parties": args.parties,
                "L": args.L,
                "repetition": repetition,
                "protocol": args.protocol,
                "batch_size": args.batch_size,
                "baseline_seconds": baseline_seconds,
                "mpc_runtime_seconds": secure.metrics.runtime_seconds,
                "mpc_wall_seconds": secure.wall_seconds,
                "encoding_seconds": secure.encoding_seconds,
                "global_communication_mb": secure.metrics.global_communication_mb,
                "max_party_communication_mb": secure.metrics.max_party_communication_mb,
                "rounds": secure.metrics.max_rounds,
                "overhead_ratio": secure.metrics.runtime_seconds / baseline_seconds,
                "expected_checksum": int(expected.sum()),
                "correct": secure.correct,
            }
            append_csv(args.output, row)
            print(
                f"D={dimension} repetition={repetition + 1}/{args.repetitions}: "
                f"plain={baseline_seconds:.6f}s, MPC={secure.metrics.runtime_seconds:.6f}s, "
                f"communication={secure.metrics.global_communication_mb:.3f} MB",
                flush=True,
            )


if __name__ == "__main__":
    main()
