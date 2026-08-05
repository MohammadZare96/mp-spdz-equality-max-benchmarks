#!/usr/bin/env python3
"""Benchmark Extended SCG value-and-index selection for varying K=N."""

from __future__ import annotations

import argparse
import random
import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.extension_common import (
    append_csv,
    compile_program,
    install_program,
    run_schedule,
    write_player_inputs,
)
from benchmarks.run_benchmarks import PRIMES, SCALE_VALUES, encode


MAX_RE = re.compile(r"^ESCG_MAX\s+(-?[0-9]+)", re.MULTILINE)
INDEX_RE = re.compile(r"^ESCG_INDEX\s+(-?[0-9]+)", re.MULTILINE)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mp-spdz", required=True, type=Path)
    parser.add_argument("--sizes", nargs="+", type=int, default=SCALE_VALUES)
    parser.add_argument("--L", type=int, default=32)
    parser.add_argument("--protocol", choices=("semi", "shamir"), default="semi")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20260805)
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--output", type=Path, default=Path("results/escg-raw.csv"))
    args = parser.parse_args()
    mp_spdz = args.mp_spdz.resolve()
    prime = PRIMES[args.L]
    install_program(mp_spdz, "extended_scg")

    for size in args.sizes:
        if size < 2:
            raise SystemExit("all ESCG sizes must be >= 2")
        schedule = compile_program(
            mp_spdz,
            "extended_scg",
            prime,
            [args.L, size, size, prime],
        )
        for repetition in range(args.repetitions):
            rng = random.Random(args.seed ^ (size << 16) ^ repetition)
            values = rng.sample(range(2 ** (args.L - 1), prime), size)
            expected_max = max(values)
            expected_index = values.index(expected_max)
            per_party: list[list[int]] = [[] for _ in range(size)]
            for index, value in enumerate(values):
                per_party[index].extend(encode(value, args.L, prime, rng))
            write_player_inputs(mp_spdz, per_party)
            metrics = run_schedule(
                mp_spdz,
                protocol=args.protocol,
                schedule=schedule,
                parties=size,
                batch_size=args.batch_size,
                timeout=args.timeout,
            )
            observed_maxes = MAX_RE.findall(metrics.output)
            observed_indices = INDEX_RE.findall(metrics.output)
            if not observed_maxes or not observed_indices:
                raise ValueError("missing Extended SCG result markers")
            observed_max = int(observed_maxes[0]) % prime
            observed_index = int(observed_indices[0])
            correct = observed_max == expected_max and observed_index == expected_index
            if not correct:
                raise RuntimeError(
                    f"incorrect ESCG result: got ({observed_max}, {observed_index}), "
                    f"expected ({expected_max}, {expected_index})"
                )
            row = {
                "K": size,
                "N": size,
                "L": args.L,
                "repetition": repetition,
                "protocol": args.protocol,
                "batch_size": args.batch_size,
                "runtime_seconds": metrics.runtime_seconds,
                "global_communication_mb": metrics.global_communication_mb,
                "max_party_communication_mb": metrics.max_party_communication_mb,
                "rounds": metrics.max_rounds,
                "observed_max": observed_max,
                "expected_max": expected_max,
                "observed_index": observed_index,
                "expected_index": expected_index,
                "correct": correct,
            }
            append_csv(args.output, row)
            print(
                f"K=N={size} repetition={repetition + 1}/{args.repetitions}: "
                f"{metrics.runtime_seconds:.6f}s, "
                f"{metrics.global_communication_mb:.3f} MB",
                flush=True,
            )


if __name__ == "__main__":
    main()
