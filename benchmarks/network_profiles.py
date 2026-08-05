#!/usr/bin/env python3
"""Apply reproducible trace-based LAN/WAN timing models to MP-SPDZ results.

The model adds one configured one-way latency per reported MPC round and the
serialization time for all globally communicated bytes. It is intentionally
labelled as an estimate, not a packet-level measurement.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


DEFAULT_PROFILES = {
    "LAN": {"latency_ms": 1.0, "bandwidth_mbps": 1_000.0},
    "WAN": {"latency_ms": 50.0, "bandwidth_mbps": 100.0},
}


def estimate_runtime(
    local_runtime_seconds: float,
    global_communication_mb: float,
    rounds: int,
    *,
    latency_ms: float,
    bandwidth_mbps: float,
) -> float:
    if min(local_runtime_seconds, global_communication_mb, rounds) < 0:
        raise ValueError("runtime, communication, and rounds must be non-negative")
    if latency_ms < 0 or bandwidth_mbps <= 0:
        raise ValueError("latency must be non-negative and bandwidth positive")
    latency_cost = rounds * latency_ms / 1_000
    serialization_cost = global_communication_mb * 8 / bandwidth_mbps
    return local_runtime_seconds + latency_cost + serialization_cost


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--runtime-field", default="runtime_seconds")
    parser.add_argument("--communication-field", default="global_communication_mb")
    parser.add_argument("--rounds-field", default="rounds")
    parser.add_argument("--lan-latency-ms", type=float, default=1.0)
    parser.add_argument("--lan-bandwidth-mbps", type=float, default=1_000.0)
    parser.add_argument("--wan-latency-ms", type=float, default=50.0)
    parser.add_argument("--wan-bandwidth-mbps", type=float, default=100.0)
    args = parser.parse_args()
    profiles = {
        "LAN": {
            "latency_ms": args.lan_latency_ms,
            "bandwidth_mbps": args.lan_bandwidth_mbps,
        },
        "WAN": {
            "latency_ms": args.wan_latency_ms,
            "bandwidth_mbps": args.wan_bandwidth_mbps,
        },
    }

    with args.input.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("input CSV is empty")
    output_rows = []
    for row in rows:
        for profile_name, profile in profiles.items():
            estimated = estimate_runtime(
                float(row[args.runtime_field]),
                float(row[args.communication_field]),
                int(row[args.rounds_field]),
                **profile,
            )
            output_rows.append(
                {
                    **row,
                    "network_profile": profile_name,
                    **profile,
                    "estimated_runtime_seconds": estimated,
                    "estimate_method": "round-and-byte trace model",
                }
            )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)


if __name__ == "__main__":
    main()
