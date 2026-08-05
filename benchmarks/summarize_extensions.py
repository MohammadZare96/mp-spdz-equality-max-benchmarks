#!/usr/bin/env python3
"""Create compact median/IQR tables for Median, ESCG, network, and MNIST."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import numpy as np


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def stats(values: list[float]) -> dict[str, float]:
    data = np.asarray(values, dtype=float)
    return {
        "median": float(np.median(data)),
        "p25": float(np.percentile(data, 25)),
        "p75": float(np.percentile(data, 75)),
    }


def emit(path: Path, output: list[dict[str, object]]) -> None:
    if not output:
        raise ValueError(f"no summary rows for {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output[0]))
        writer.writeheader()
        writer.writerows(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results_dir", type=Path, nargs="?", default=Path("results"))
    args = parser.parse_args()
    root = args.results_dir

    median_groups: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in rows(root / "median-vector-raw.csv"):
        median_groups[int(row["dimension"])].append(row)
    median_out = []
    for dimension, group in sorted(median_groups.items()):
        plain = stats([float(row["baseline_seconds"]) for row in group])
        secure = stats([float(row["mpc_runtime_seconds"]) for row in group])
        comm = stats([float(row["global_communication_mb"]) for row in group])
        median_out.append({
            "dimension": dimension,
            "clients": int(group[0]["clients"]),
            "parties": int(group[0]["parties"]),
            "L": int(group[0]["L"]),
            "protocol": group[0]["protocol"],
            "plaintext_median_seconds": plain["median"],
            "plaintext_p25_seconds": plain["p25"],
            "plaintext_p75_seconds": plain["p75"],
            "mpc_median_seconds": secure["median"],
            "mpc_p25_seconds": secure["p25"],
            "mpc_p75_seconds": secure["p75"],
            "communication_median_mb": comm["median"],
            "overhead_ratio": secure["median"] / plain["median"],
            "repetitions": len(group),
        })
    emit(root / "median-vector-summary.csv", median_out)

    escg_groups: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in rows(root / "escg-raw.csv"):
        escg_groups[int(row["N"])].append(row)
    escg_out = []
    for parties, group in sorted(escg_groups.items()):
        runtime = stats([float(row["runtime_seconds"]) for row in group])
        comm = stats([float(row["global_communication_mb"]) for row in group])
        escg_out.append({
            "N": parties,
            "K": int(group[0]["K"]),
            "L": int(group[0]["L"]),
            "protocol": group[0]["protocol"],
            "runtime_median_seconds": runtime["median"],
            "runtime_p25_seconds": runtime["p25"],
            "runtime_p75_seconds": runtime["p75"],
            "communication_median_mb": comm["median"],
            "communication_p25_mb": comm["p25"],
            "communication_p75_mb": comm["p75"],
            "rounds": int(np.median([int(row["rounds"]) for row in group])),
            "repetitions": len(group),
        })
    emit(root / "escg-summary.csv", escg_out)

    network_groups: dict[tuple[int, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows(root / "escg-network-profiles.csv"):
        network_groups[(int(row["N"]), row["network_profile"])].append(row)
    network_out = []
    for (parties, profile), group in sorted(network_groups.items()):
        estimate = stats([float(row["estimated_runtime_seconds"]) for row in group])
        network_out.append({
            "N": parties,
            "network_profile": profile,
            "latency_ms": float(group[0]["latency_ms"]),
            "bandwidth_mbps": float(group[0]["bandwidth_mbps"]),
            "estimated_runtime_median_seconds": estimate["median"],
            "estimated_runtime_p25_seconds": estimate["p25"],
            "estimated_runtime_p75_seconds": estimate["p75"],
            "estimate_method": group[0]["estimate_method"],
        })
    emit(root / "escg-network-summary.csv", network_out)


if __name__ == "__main__":
    main()
