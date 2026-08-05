#!/usr/bin/env python3
"""Compile, run, verify, and record the requested MP-SPDZ benchmarks."""

from __future__ import annotations

import argparse
import csv
import os
import random
import re
import shutil
import statistics
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence


ROOT = Path(__file__).resolve().parents[1]
MPC_SOURCE = ROOT / "mpc"

L_VALUES = (8, 16, 32, 64)
SCALE_VALUES = (2, 4, 8, 10, 20, 30, 40, 50)
PRIMES = {
    8: 251,
    16: 65_521,
    32: 4_294_967_291,
    64: 18_446_744_073_709_551_557,
}

TIME_RE = re.compile(r"^Time = ([0-9.eE+-]+) seconds", re.MULTILINE)
GLOBAL_COMM_RE = re.compile(
    r"^Global data sent = ([0-9.eE+-]+) MB \(all parties\)", re.MULTILINE
)
PARTY_COMM_RE = re.compile(
    r"^Data sent = ([0-9.eE+-]+) MB in ~([0-9]+) rounds", re.MULTILINE
)
RESULT_RE = {
    "equality": re.compile(r"^EQUALITY_RESULT\s+(-?[0-9]+)", re.MULTILINE),
    "max": re.compile(r"^MAX_RESULT\s+(-?[0-9]+)", re.MULTILINE),
}


@dataclass(frozen=True)
class Case:
    sweep: str
    operation: str
    L: int
    K: int
    N: int

    @property
    def prime(self) -> int:
        return PRIMES[self.L]

    @property
    def schedule(self) -> str:
        return f"{self.operation}-{self.L}-{self.K}-{self.N}-{self.prime}"


@dataclass
class Result:
    sweep: str
    operation: str
    L: int
    K: int
    N: int
    repetition: int
    protocol: str
    preprocessing_batch_size: int
    prime: int
    runtime_seconds: float
    global_communication_mb: float
    max_party_communication_mb: float
    max_rounds: int
    observed_result: int
    expected_result: int
    correct: bool


def requested_cases() -> list[Case]:
    """Return the exact four experiment families requested by the user."""
    cases: list[Case] = []
    for operation in ("equality", "max"):
        cases.extend(
            Case("vary_L", operation, L, 8, 8)
            for L in L_VALUES
        )
        cases.extend(
            Case("vary_KN", operation, 32, size, size)
            for size in SCALE_VALUES
        )
    return cases


def partition_vector(value: int, L: int) -> list[int]:
    bits = f"{value:0{L}b}"
    if len(bits) != L or bits[0] != "1":
        raise ValueError(f"value must have exactly {L} bits")
    return [int(bits[:i], 2) for i in range(1, L + 1)]


def zero_coded_vector(value: int, L: int, prime: int, rng: random.Random) -> list[int]:
    bits = f"{value:0{L}b}"
    if len(bits) != L or bits[0] != "1":
        raise ValueError(f"value must have exactly {L} bits")

    encoded: list[int] = []
    for index, bit in enumerate(bits, start=1):
        if bit == "0":
            encoded.append(int(bits[: index - 1] + "1", 2))
            continue

        # Paper definition: r_i is a random binary value whose bit length is
        # not i. Exact-L-bit inputs ensure this cannot equal an i-bit prefix.
        candidate = rng.randrange(prime)
        while candidate.bit_length() == index:
            candidate = rng.randrange(prime)
        encoded.append(candidate)
    return encoded


def encode(value: int, L: int, prime: int, rng: random.Random) -> list[int]:
    if not (2 ** (L - 1) <= value < prime):
        raise ValueError(f"value must be an L-bit field element below {prime}")
    return partition_vector(value, L) + zero_coded_vector(value, L, prime, rng)


def prepare_inputs(
    mp_spdz: Path, case: Case, repetition: int, seed: int
) -> int:
    rng = random.Random((seed << 32) ^ (case.L << 24) ^ (case.K << 8) ^ repetition)
    per_party: list[list[int]] = [[] for _ in range(case.N)]

    if case.operation == "equality":
        left = rng.randrange(2 ** (case.L - 1), case.prime)
        if repetition % 2 == 0:
            right = left
            expected = 0
        else:
            right = rng.randrange(2 ** (case.L - 1), case.prime)
            while right == left:
                right = rng.randrange(2 ** (case.L - 1), case.prime)
            expected = 1
        per_party[0].append(left)
        per_party[1].append(right)
    else:
        values = [
            rng.randrange(2 ** (case.L - 1), case.prime)
            for _ in range(case.K)
        ]
        expected = max(values)
        for index, value in enumerate(values):
            per_party[index % case.N].extend(
                encode(value, case.L, case.prime, rng)
            )

    player_data = mp_spdz / "Player-Data"
    player_data.mkdir(exist_ok=True)
    for party, values in enumerate(per_party):
        (player_data / f"Input-P{party}-0").write_text(
            " ".join(map(str, values)) + "\n", encoding="ascii"
        )
    return expected


def install_sources(mp_spdz: Path) -> None:
    destination = mp_spdz / "Programs" / "Source"
    if not destination.is_dir():
        raise FileNotFoundError(f"not an MP-SPDZ checkout: {mp_spdz}")
    for operation in ("equality", "max"):
        shutil.copy2(MPC_SOURCE / f"{operation}.mpc", destination / f"{operation}.mpc")


def run_checked(
    command: Sequence[str], *, cwd: Path, env: dict[str, str] | None = None,
    timeout: int | None = None
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
    )
    if completed.returncode:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n"
            f"{completed.stdout}"
        )
    return completed


def compile_case(mp_spdz: Path, case: Case) -> None:
    run_checked(
        [
            sys.executable,
            "compile.py",
            "-P",
            str(case.prime),
            case.operation,
            str(case.L),
            str(case.K),
            str(case.N),
            str(case.prime),
        ],
        cwd=mp_spdz,
    )


def parse_party_logs(logs: Iterable[Path], operation: str) -> tuple[float, float, float, int, int]:
    runtimes: list[float] = []
    global_comms: list[float] = []
    party_comms: list[float] = []
    rounds: list[int] = []
    observed: list[int] = []

    for log in logs:
        content = log.read_text(encoding="utf-8", errors="replace")
        runtimes.extend(float(value) for value in TIME_RE.findall(content))
        global_comms.extend(float(value) for value in GLOBAL_COMM_RE.findall(content))
        for comm, round_count in PARTY_COMM_RE.findall(content):
            party_comms.append(float(comm))
            rounds.append(int(round_count))
        observed.extend(int(value) for value in RESULT_RE[operation].findall(content))

    if not runtimes or not global_comms or not party_comms or not observed:
        raise ValueError("MP-SPDZ output did not contain all expected metrics/result markers")
    if len(set(observed)) != 1:
        raise ValueError(f"parties disagreed on output: {observed}")

    return (
        max(runtimes),
        max(global_comms),
        max(party_comms),
        max(rounds),
        observed[0],
    )


def execute_case(
    mp_spdz: Path,
    case: Case,
    protocol: str,
    repetition: int,
    expected: int,
    batch_size: int,
    timeout: int,
) -> Result:
    run_id = uuid.uuid4().hex
    log_prefix = f"paper-bench-{run_id}-"
    env = os.environ.copy()
    env.update({"PLAYERS": str(case.N), "LOG_PREFIX": log_prefix})

    script = mp_spdz / "Scripts" / f"{protocol}.sh"
    if not script.exists():
        raise FileNotFoundError(f"protocol runner not found: {script}")
    if protocol == "shamir" and case.N < 3:
        raise ValueError("MP-SPDZ Shamir requires N >= 3; use --protocol semi for N=2")

    run_checked(
        [str(script), case.schedule, "--batch-size", str(batch_size)],
        cwd=mp_spdz,
        env=env,
        timeout=timeout,
    )
    logs = sorted((mp_spdz / "logs").glob(f"{log_prefix}{case.schedule}-*"))
    try:
        runtime, global_comm, party_comm, rounds, observed = parse_party_logs(
            logs, case.operation
        )
    finally:
        for log in logs:
            log.unlink(missing_ok=True)

    # MP-SPDZ prints prime-field values using centered representatives
    # (for example, 246 in F_251 is displayed as -5). Normalize opened Max
    # outputs to the canonical [0, p) representative before verification.
    if case.operation == "max":
        observed %= case.prime

    return Result(
        **asdict(case),
        repetition=repetition,
        protocol=protocol,
        preprocessing_batch_size=batch_size,
        prime=case.prime,
        runtime_seconds=runtime,
        global_communication_mb=global_comm,
        max_party_communication_mb=party_comm,
        max_rounds=rounds,
        observed_result=observed,
        expected_result=expected,
        correct=(observed == expected),
    )


def append_result(path: Path, result: Result) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(result)))
        if not exists:
            writer.writeheader()
        writer.writerow(asdict(result))


def select_cases(args: argparse.Namespace) -> list[Case]:
    cases = requested_cases()
    if args.operation != "all":
        cases = [case for case in cases if case.operation == args.operation]
    if args.sweep != "all":
        cases = [case for case in cases if case.sweep == args.sweep]
    if args.protocol == "shamir" and any(case.N == 2 for case in cases):
        print(
            "Skipping N=2: MP-SPDZ Shamir requires at least three parties. ",
            "Use --protocol semi to run the exact requested matrix.",
            file=sys.stderr,
        )
        cases = [case for case in cases if case.N >= 3]
    return cases


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mp-spdz", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "raw.csv")
    parser.add_argument("--protocol", choices=("semi", "shamir"), default="semi")
    parser.add_argument("--operation", choices=("all", "equality", "max"), default="all")
    parser.add_argument("--sweep", choices=("all", "vary_L", "vary_KN"), default="all")
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help=(
            "MP-SPDZ preprocessing batch size. The conservative default keeps "
            "the requested 50-party cases within practical memory limits."
        ),
    )
    parser.add_argument("--seed", type=int, default=20260805)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--no-compile", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    mp_spdz = args.mp_spdz.resolve()
    if args.repetitions < 1:
        raise SystemExit("--repetitions must be positive")
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be positive")

    install_sources(mp_spdz)
    cases = select_cases(args)
    all_results: list[Result] = []

    for index, case in enumerate(cases, start=1):
        print(
            f"[{index}/{len(cases)}] {case.operation} {case.sweep}: "
            f"L={case.L}, K={case.K}, N={case.N}",
            flush=True,
        )
        if not args.no_compile:
            compile_case(mp_spdz, case)
        for repetition in range(args.repetitions):
            expected = prepare_inputs(mp_spdz, case, repetition, args.seed)
            started = time.monotonic()
            result = execute_case(
                mp_spdz,
                case,
                args.protocol,
                repetition,
                expected,
                args.batch_size,
                args.timeout,
            )
            if not result.correct:
                raise RuntimeError(
                    f"wrong {case.operation} result: expected {expected}, "
                    f"observed {result.observed_result}"
                )
            append_result(args.output, result)
            all_results.append(result)
            print(
                f"  repetition {repetition + 1}/{args.repetitions}: "
                f"{result.runtime_seconds:.6f}s, "
                f"{result.global_communication_mb:.6f} MB global "
                f"(wall {time.monotonic() - started:.2f}s)",
                flush=True,
            )

    if all_results:
        print(
            f"Wrote {len(all_results)} verified runs to {args.output}. "
            f"Median runtime: {statistics.median(r.runtime_seconds for r in all_results):.6f}s"
        )


if __name__ == "__main__":
    main()
