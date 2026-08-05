#!/usr/bin/env python3
"""Plot Median, Extended SCG, network-profile, and federated-MNIST results."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


COLORS = {"plain": "#2a9d8f", "secure": "#e76f51", "LAN": "#3a86ff", "WAN": "#ff006e"}


def load(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def save(figure: plt.Figure, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(target.with_suffix(".pdf"), bbox_inches="tight")
    figure.savefig(target.with_suffix(".png"), dpi=220, bbox_inches="tight")
    plt.close(figure)


def median_runtime(results: Path, output: Path) -> None:
    data = load(results / "median-vector-summary.csv")
    x = [int(row["dimension"]) for row in data]
    figure, axis = plt.subplots(figsize=(6.8, 4.3), constrained_layout=True)
    for field, p25, p75, label, color, marker in (
        ("plaintext_median_seconds", "plaintext_p25_seconds", "plaintext_p75_seconds", "Plaintext NumPy", COLORS["plain"], "o"),
        ("mpc_median_seconds", "mpc_p25_seconds", "mpc_p75_seconds", "Paper median in MP-SPDZ", COLORS["secure"], "s"),
    ):
        y = [float(row[field]) for row in data]
        low = [float(row[p25]) for row in data]
        high = [float(row[p75]) for row in data]
        axis.plot(x, y, marker=marker, linewidth=2.2, label=label, color=color)
        axis.fill_between(x, low, high, alpha=.16, color=color)
    axis.set(xscale="log", yscale="log", xlabel="Gradient-vector dimension", ylabel="Runtime (seconds)", title="Coordinate-wise median runtime, 10 clients")
    axis.set_xticks(x, labels=[f"{value:,}" for value in x])
    axis.grid(True, which="both", alpha=.22)
    axis.legend(frameon=False)
    save(figure, output / "median_vector_runtime")


def escg_runtime(results: Path, output: Path) -> None:
    data = load(results / "escg-summary.csv")
    x = [int(row["N"]) for row in data]
    median = [float(row["runtime_median_seconds"]) for row in data]
    low = [float(row["runtime_p25_seconds"]) for row in data]
    high = [float(row["runtime_p75_seconds"]) for row in data]
    figure, axis = plt.subplots(figsize=(6.8, 4.3), constrained_layout=True)
    axis.plot(x, median, marker="o", linewidth=2.2, color="#8338ec", label="Measured loopback")
    axis.fill_between(x, low, high, alpha=.16, color="#8338ec", label="IQR")
    axis.set(yscale="log", xlabel="Inputs and parties K=N", ylabel="Runtime (seconds)", title="Extended SCG: max value plus secret index")
    axis.set_xticks(x)
    axis.grid(True, which="both", alpha=.22)
    axis.legend(frameon=False)
    axis.text(.01, -.22, "Batch size 500 for N≤40 and 400 for N=50; every point passed a value-and-index correctness check.", transform=axis.transAxes, fontsize=8, color="#666")
    save(figure, output / "escg_runtime")


def network_runtime(results: Path, output: Path) -> None:
    data = load(results / "escg-network-summary.csv")
    figure, axis = plt.subplots(figsize=(6.8, 4.3), constrained_layout=True)
    for profile in ("LAN", "WAN"):
        selected = [row for row in data if row["network_profile"] == profile]
        x = [int(row["N"]) for row in selected]
        y = [float(row["estimated_runtime_median_seconds"]) for row in selected]
        axis.plot(x, y, marker="o", linewidth=2.2, label=f"{profile} estimate", color=COLORS[profile])
    axis.set(yscale="log", xlabel="Inputs and parties K=N", ylabel="Estimated runtime (seconds)", title="Extended SCG under modeled LAN and WAN")
    axis.set_xticks(sorted({int(row["N"]) for row in data}))
    axis.grid(True, which="both", alpha=.22)
    axis.legend(frameon=False)
    axis.text(.01, -.22, "Trace model: local runtime + rounds×latency + bytes/bandwidth; not a packet-level measurement.", transform=axis.transAxes, fontsize=8, color="#666")
    save(figure, output / "escg_network_profiles")


def mnist(results: Path, output: Path) -> None:
    data = load(results / "mnist-fl-median.csv")
    figure, axes = plt.subplots(1, 2, figsize=(10.8, 4.1), constrained_layout=True)
    for mode, label, color, marker in (
        ("plaintext", "Plaintext median", COLORS["plain"], "o"),
        ("paper_mpc", "Paper median in MP-SPDZ", COLORS["secure"], "s"),
    ):
        selected = [row for row in data if row["mode"] == mode]
        x = [int(row["round"]) for row in selected]
        axes[0].plot(x, [100 * float(row["test_accuracy"]) for row in selected], marker=marker, linewidth=2.2, color=color, label=label, alpha=.9)
        axes[1].bar([value + (-.17 if mode == "plaintext" else .17) for value in x], [float(row["aggregation_wall_seconds"]) for row in selected], width=.34, color=color, label=label)
    axes[0].set(xlabel="Federated round", ylabel="Test accuracy (%)", title="MNIST accuracy")
    axes[0].text(.03, .05, "The two accuracy curves overlap exactly.", transform=axes[0].transAxes, fontsize=8, color="#666")
    axes[1].set(xlabel="Federated round", ylabel="Aggregation wall time (seconds)", title="Median aggregation overhead", yscale="log", xticks=[1, 2, 3])
    for axis in axes:
        axis.grid(True, axis="y", alpha=.22)
        axis.legend(frameon=False, fontsize=8)
    save(figure, output / "mnist_federated_median")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results_dir", type=Path, nargs="?", default=Path("results"))
    parser.add_argument("output_dir", type=Path, nargs="?", default=Path("results/figures"))
    args = parser.parse_args()
    median_runtime(args.results_dir, args.output_dir)
    escg_runtime(args.results_dir, args.output_dir)
    network_runtime(args.results_dir, args.output_dir)
    mnist(args.results_dir, args.output_dir)


if __name__ == "__main__":
    main()
