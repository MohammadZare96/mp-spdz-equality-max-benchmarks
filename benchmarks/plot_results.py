#!/usr/bin/env python3
"""Create the four requested runtime/communication comparison figures."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


OPERATIONS = ("equality", "max")
STYLE = {
    "equality": {"label": "Equality", "marker": "o"},
    "max": {"label": "Max", "marker": "s"},
}
FIGURES = (
    ("vary_L", "runtime", "Equality and Max runtime (K=N=8)", "Runtime (seconds)"),
    ("vary_L", "communication", "Equality and Max communication (K=N=8)", "Global communication (MB)"),
    ("vary_KN", "runtime", "Equality and Max runtime (L=32)", "Runtime (seconds)"),
    ("vary_KN", "communication", "Equality and Max communication (L=32)", "Global communication (MB)"),
)


def load_rows(path: Path, protocol: str) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if row["protocol"] == protocol]
    if not rows:
        raise ValueError(f"no rows for protocol {protocol!r} in {path}")
    return rows


def metric_fields(metric: str) -> tuple[str, str, str]:
    if metric == "runtime":
        return (
            "runtime_median_seconds",
            "runtime_p25_seconds",
            "runtime_p75_seconds",
        )
    return (
        "communication_median_mb",
        "communication_p25_mb",
        "communication_p75_mb",
    )


def plot_one(
    rows: list[dict[str, str]],
    sweep: str,
    metric: str,
    title: str,
    ylabel: str,
    output: Path,
    log_y: bool,
) -> None:
    x_field = "L" if sweep == "vary_L" else "K"
    median_field, p25_field, p75_field = metric_fields(metric)

    figure, axis = plt.subplots(figsize=(6.4, 4.2), constrained_layout=True)
    for operation in OPERATIONS:
        selected = sorted(
            (
                row
                for row in rows
                if row["sweep"] == sweep and row["operation"] == operation
            ),
            key=lambda row: int(row[x_field]),
        )
        if not selected:
            raise ValueError(f"missing {sweep}/{operation} rows")
        x = [int(row[x_field]) for row in selected]
        median = [float(row[median_field]) for row in selected]
        p25 = [float(row[p25_field]) for row in selected]
        p75 = [float(row[p75_field]) for row in selected]
        style = STYLE[operation]
        line = axis.plot(
            x,
            median,
            marker=style["marker"],
            linewidth=2,
            markersize=5,
            label=style["label"],
        )[0]
        axis.fill_between(x, p25, p75, color=line.get_color(), alpha=0.16)

    axis.set_title(title)
    axis.set_xlabel("Bit length L" if sweep == "vary_L" else "K=N")
    axis.set_ylabel(ylabel)
    axis.set_xticks(sorted({int(row[x_field]) for row in rows if row["sweep"] == sweep}))
    if log_y:
        axis.set_yscale("log")
    axis.grid(True, which="major", axis="both", alpha=0.25)
    axis.legend(frameon=False)

    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output.with_suffix(".pdf"), bbox_inches="tight")
    figure.savefig(output.with_suffix(".png"), dpi=220, bbox_inches="tight")
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--protocol", choices=("semi", "shamir"), default="semi")
    parser.add_argument("--log-y", action="store_true")
    args = parser.parse_args()

    rows = load_rows(args.summary, args.protocol)
    for sweep, metric, title, ylabel in FIGURES:
        filename = f"{sweep}_{metric}"
        plot_one(
            rows,
            sweep,
            metric,
            title,
            ylabel,
            args.output_dir / filename,
            args.log_y,
        )


if __name__ == "__main__":
    main()
