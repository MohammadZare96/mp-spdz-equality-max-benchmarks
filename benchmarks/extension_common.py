"""Shared MP-SPDZ execution helpers for the extension experiments."""

from __future__ import annotations

import os
import shutil
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

from benchmarks.run_benchmarks import (
    GLOBAL_COMM_RE,
    PARTY_COMM_RE,
    ROOT,
    TIME_RE,
    run_checked,
)


@dataclass(frozen=True)
class ExecutionMetrics:
    runtime_seconds: float
    global_communication_mb: float
    max_party_communication_mb: float
    max_rounds: int
    output: str


def install_program(mp_spdz: Path, program_name: str) -> None:
    source = ROOT / "mpc" / f"{program_name}.mpc"
    destination = mp_spdz / "Programs" / "Source" / source.name
    if not destination.parent.is_dir():
        raise FileNotFoundError(f"not an MP-SPDZ checkout: {mp_spdz}")
    shutil.copy2(source, destination)


def compile_program(
    mp_spdz: Path,
    program_name: str,
    prime: int,
    arguments: list[int],
) -> str:
    run_checked(
        [
            os.fspath(Path(sys.executable)),
            "compile.py",
            "-P",
            str(prime),
            program_name,
            *(str(value) for value in arguments),
        ],
        cwd=mp_spdz,
    )
    return f"{program_name}-{'-'.join(map(str, arguments))}"


def write_player_inputs(mp_spdz: Path, per_party: list[list[int]]) -> None:
    player_data = mp_spdz / "Player-Data"
    player_data.mkdir(exist_ok=True)
    for party, values in enumerate(per_party):
        (player_data / f"Input-P{party}-0").write_text(
            " ".join(map(str, values)) + "\n",
            encoding="ascii",
        )


def run_schedule(
    mp_spdz: Path,
    *,
    protocol: str,
    schedule: str,
    parties: int,
    batch_size: int,
    timeout: int,
    extra_party_options: list[str] | None = None,
) -> ExecutionMetrics:
    run_id = uuid.uuid4().hex
    log_prefix = f"extension-bench-{run_id}-"
    env = os.environ.copy()
    env.update({"PLAYERS": str(parties), "LOG_PREFIX": log_prefix})
    script = mp_spdz / "Scripts" / f"{protocol}.sh"
    if not script.exists():
        raise FileNotFoundError(f"protocol runner not found: {script}")
    if protocol == "shamir" and parties < 3:
        raise ValueError("MP-SPDZ Shamir requires at least three parties")

    command = [str(script), schedule, "--batch-size", str(batch_size)]
    command.extend(extra_party_options or [])
    run_checked(command, cwd=mp_spdz, env=env, timeout=timeout)
    logs = sorted((mp_spdz / "logs").glob(f"{log_prefix}{schedule}-*"))
    try:
        contents = [path.read_text(encoding="utf-8", errors="replace") for path in logs]
    finally:
        for path in logs:
            path.unlink(missing_ok=True)

    combined = "\n".join(contents)
    runtimes = [float(value) for value in TIME_RE.findall(combined)]
    global_comms = [float(value) for value in GLOBAL_COMM_RE.findall(combined)]
    party_metrics = PARTY_COMM_RE.findall(combined)
    if not runtimes or not global_comms or not party_metrics:
        raise ValueError("MP-SPDZ output did not contain all required metrics")
    return ExecutionMetrics(
        runtime_seconds=max(runtimes),
        global_communication_mb=max(global_comms),
        max_party_communication_mb=max(float(value) for value, _ in party_metrics),
        max_rounds=max(int(rounds) for _, rounds in party_metrics),
        output=combined,
    )


def append_csv(path: Path, row: dict[str, object]) -> None:
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        if not exists:
            writer.writeheader()
        writer.writerow(row)
