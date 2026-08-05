"""Prepare and execute the paper's SIMD coordinate-wise median in MP-SPDZ."""

from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from benchmarks.extension_common import (
    ExecutionMetrics,
    compile_program,
    install_program,
    run_schedule,
    write_player_inputs,
)
from benchmarks.run_benchmarks import PRIMES, encode


CHECKSUM_RE = re.compile(r"^MEDIAN_CHECKSUM\s+(-?[0-9]+)", re.MULTILINE)
FIRST_RE = re.compile(r"^MEDIAN_FIRST\s+(-?[0-9]+)", re.MULTILINE)
LAST_RE = re.compile(r"^MEDIAN_LAST\s+(-?[0-9]+)", re.MULTILINE)
VALUE_RE = re.compile(r"^MEDIAN_VALUE\s+(-?[0-9]+)", re.MULTILINE)


@dataclass(frozen=True)
class SecureMedianResult:
    median: np.ndarray | None
    metrics: ExecutionMetrics
    encoding_seconds: float
    wall_seconds: float
    correct: bool


def upper_median(values: np.ndarray) -> np.ndarray:
    """Return the paper-compatible upper median for an even client count."""
    if values.ndim != 2 or values.shape[0] < 2 or values.shape[0] % 2:
        raise ValueError("values must have shape (even clients, dimensions)")
    return np.partition(values, values.shape[0] // 2, axis=0)[values.shape[0] // 2]


def distinct_random_matrix(
    *, clients: int, dimension: int, L: int, seed: int
) -> np.ndarray:
    """Generate exact-L-bit values that are distinct per coordinate."""
    if clients % 2 or clients < 2:
        raise ValueError("clients must be an even integer >= 2")
    prime = PRIMES[L]
    low = 2 ** (L - 1)
    if prime - low <= clients:
        raise ValueError("field range is too small for unique client values")
    rng = np.random.default_rng(seed)
    bases = rng.integers(low, prime - clients, size=dimension, dtype=np.int64)
    offsets = np.argsort(rng.random((clients, dimension)), axis=0)
    return bases[None, :] + offsets


def encode_matrix(
    values: np.ndarray,
    *,
    L: int,
    prime: int,
    parties: int,
    seed: int,
) -> list[list[int]]:
    """Encode client vectors in the column-major layout used by SIMD MPC."""
    clients, dimension = values.shape
    per_party: list[list[int]] = [[] for _ in range(parties)]
    rng = random.Random(seed)
    for client in range(clients):
        columns = [[] for _ in range(2 * L)]
        for coordinate in range(dimension):
            encoded = encode(int(values[client, coordinate]), L, prime, rng)
            for position, value in enumerate(encoded):
                columns[position].append(value)
        owner = client % parties
        for column in columns:
            per_party[owner].extend(column)
    return per_party


def run_secure_median(
    values: np.ndarray,
    *,
    mp_spdz: Path,
    L: int = 16,
    parties: int | None = None,
    protocol: str = "semi",
    batch_size: int = 500,
    timeout: int = 3600,
    seed: int = 20260805,
    reveal_all: bool = False,
    compile_source: bool = True,
) -> SecureMedianResult:
    clients, dimension = values.shape
    parties = parties or clients
    prime = PRIMES[L]
    if np.any(values < 2 ** (L - 1)) or np.any(values >= prime):
        raise ValueError("all encoded values must be exact-L-bit elements below the prime")
    expected = upper_median(values).astype(np.int64)

    if compile_source:
        install_program(mp_spdz, "median_vector")
        schedule = compile_program(
            mp_spdz,
            "median_vector",
            prime,
            [L, clients, parties, dimension, prime, int(reveal_all)],
        )
    else:
        schedule = (
            f"median_vector-{L}-{clients}-{parties}-{dimension}-{prime}-"
            f"{int(reveal_all)}"
        )

    started_encoding = time.perf_counter()
    encoded = encode_matrix(
        values,
        L=L,
        prime=prime,
        parties=parties,
        seed=seed,
    )
    write_player_inputs(mp_spdz, encoded)
    encoding_seconds = time.perf_counter() - started_encoding

    started_wall = time.perf_counter()
    metrics = run_schedule(
        mp_spdz,
        protocol=protocol,
        schedule=schedule,
        parties=parties,
        batch_size=batch_size,
        timeout=timeout,
    )
    wall_seconds = time.perf_counter() - started_wall

    def one(pattern: re.Pattern[str]) -> int:
        matches = pattern.findall(metrics.output)
        if not matches:
            raise ValueError(f"missing median result marker {pattern.pattern}")
        return int(matches[0]) % prime

    correct = (
        one(CHECKSUM_RE) == int(expected.sum() % prime)
        and one(FIRST_RE) == int(expected[0])
        and one(LAST_RE) == int(expected[-1])
    )
    revealed: np.ndarray | None = None
    if reveal_all:
        values_out = [int(value) % prime for value in VALUE_RE.findall(metrics.output)]
        if len(values_out) != dimension:
            raise ValueError(
                f"expected {dimension} revealed median values, got {len(values_out)}"
            )
        revealed = np.asarray(values_out, dtype=np.int64)
        correct = correct and np.array_equal(revealed, expected)

    return SecureMedianResult(
        median=revealed,
        metrics=metrics,
        encoding_seconds=encoding_seconds,
        wall_seconds=wall_seconds,
        correct=correct,
    )
