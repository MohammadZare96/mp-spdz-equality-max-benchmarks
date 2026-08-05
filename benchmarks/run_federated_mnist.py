#!/usr/bin/env python3
"""Train a small federated MNIST classifier with plaintext or paper median.

The model downsamples MNIST images to 7x7 and trains a softmax classifier with
500 parameters. Ten clients compute local full-batch gradients. The server
aggregates them coordinate-wise with either NumPy's upper median or the paper's
SCI rank algorithm executed by MP-SPDZ.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
import urllib.request
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from benchmarks.run_benchmarks import PRIMES
from benchmarks.secure_median import run_secure_median, upper_median


MNIST_URL = "https://storage.googleapis.com/tensorflow/tf-keras-datasets/mnist.npz"


def load_mnist(path: Path, *, download: bool) -> tuple[np.ndarray, ...]:
    if not path.exists():
        if not download:
            raise FileNotFoundError(
                f"MNIST file not found at {path}; pass --download or provide --mnist"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(MNIST_URL, path)
    with np.load(path) as data:
        x_train = np.asarray(data["x_train"], dtype=np.float64)
        y_train = np.asarray(data["y_train"], dtype=np.int64)
        x_test = np.asarray(data["x_test"], dtype=np.float64)
        y_test = np.asarray(data["y_test"], dtype=np.int64)
    return x_train, y_train, x_test, y_test


def features(images: np.ndarray) -> np.ndarray:
    """Average-pool 28x28 MNIST images to 7x7 and append no extra features."""
    if images.ndim != 3 or images.shape[1:] != (28, 28):
        raise ValueError("expected images with shape (samples, 28, 28)")
    return images.reshape(-1, 7, 4, 7, 4).mean(axis=(2, 4)) / 255.0


def pack(weights: np.ndarray, bias: np.ndarray) -> np.ndarray:
    return np.concatenate([weights.reshape(-1), bias])


def unpack(vector: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return vector[:490].reshape(49, 10), vector[490:500]


def loss_accuracy(
    vector: np.ndarray, x: np.ndarray, y: np.ndarray
) -> tuple[float, float]:
    weights, bias = unpack(vector)
    logits = x.reshape(len(x), -1) @ weights + bias
    shifted = logits - logits.max(axis=1, keepdims=True)
    probabilities = np.exp(shifted)
    probabilities /= probabilities.sum(axis=1, keepdims=True)
    loss = -np.log(probabilities[np.arange(len(y)), y] + 1e-15).mean()
    accuracy = (probabilities.argmax(axis=1) == y).mean()
    return float(loss), float(accuracy)


def client_gradient(vector: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    weights, bias = unpack(vector)
    flat = x.reshape(len(x), -1)
    logits = flat @ weights + bias
    logits -= logits.max(axis=1, keepdims=True)
    probabilities = np.exp(logits)
    probabilities /= probabilities.sum(axis=1, keepdims=True)
    probabilities[np.arange(len(y)), y] -= 1
    probabilities /= len(y)
    return pack(flat.T @ probabilities, probabilities.sum(axis=0))


def quantize_distinct(
    gradients: np.ndarray, *, L: int
) -> tuple[np.ndarray, float, int]:
    """Monotonically quantize and use the client index only to break ties."""
    clients = gradients.shape[0]
    prime = PRIMES[L]
    low = 2 ** (L - 1)
    bound = float(np.max(np.abs(gradients))) * 1.000001 + 1e-12
    buckets = (prime - low - clients - 1) // clients
    normalized = np.clip((gradients + bound) / (2 * bound), 0, 1)
    bucket = np.rint(normalized * buckets).astype(np.int64)
    codes = low + bucket * clients + np.arange(clients, dtype=np.int64)[:, None]
    if np.any(codes >= prime):
        raise ValueError("quantized median input exceeded the field prime")
    return codes, bound, buckets


def dequantize(codes: np.ndarray, *, clients: int, bound: float, buckets: int, L: int) -> np.ndarray:
    low = 2 ** (L - 1)
    bucket = (codes - low) // clients
    return bucket.astype(np.float64) / buckets * (2 * bound) - bound


def train(
    *,
    mode: str,
    initial: np.ndarray,
    client_data: list[tuple[np.ndarray, np.ndarray]],
    x_test: np.ndarray,
    y_test: np.ndarray,
    rounds: int,
    server_lr: float,
    mp_spdz: Path,
    L: int,
    protocol: str,
    batch_size: int,
    timeout: int,
    seed: int,
) -> tuple[np.ndarray, list[dict[str, object]], float]:
    model = initial.copy()
    history: list[dict[str, object]] = []
    started_training = time.perf_counter()
    for round_index in range(rounds):
        gradients = np.stack(
            [client_gradient(model, x, y) for x, y in client_data], axis=0
        )
        started_aggregation = time.perf_counter()
        communication = 0.0
        rounds_count = 0
        encoding_seconds = 0.0
        if mode == "plaintext":
            aggregate = upper_median(gradients)
            mpc_runtime = 0.0
        else:
            codes, bound, buckets = quantize_distinct(gradients, L=L)
            secure = run_secure_median(
                codes,
                mp_spdz=mp_spdz,
                L=L,
                parties=len(client_data),
                protocol=protocol,
                batch_size=batch_size,
                timeout=timeout,
                seed=seed ^ round_index,
                reveal_all=True,
                compile_source=(round_index == 0),
            )
            if not secure.correct or secure.median is None:
                raise RuntimeError(f"incorrect secure median at FL round {round_index}")
            aggregate = dequantize(
                secure.median,
                clients=len(client_data),
                bound=bound,
                buckets=buckets,
                L=L,
            )
            mpc_runtime = secure.metrics.runtime_seconds
            communication = secure.metrics.global_communication_mb
            rounds_count = secure.metrics.max_rounds
            encoding_seconds = secure.encoding_seconds
        aggregation_wall = time.perf_counter() - started_aggregation
        model -= server_lr * aggregate
        loss, accuracy = loss_accuracy(model, x_test, y_test)
        history.append(
            {
                "mode": mode,
                "round": round_index + 1,
                "test_loss": loss,
                "test_accuracy": accuracy,
                "aggregation_wall_seconds": aggregation_wall,
                "mpc_runtime_seconds": mpc_runtime,
                "encoding_seconds": encoding_seconds,
                "global_communication_mb": communication,
                "mpc_rounds": rounds_count,
            }
        )
        print(
            f"{mode} round {round_index + 1}/{rounds}: "
            f"accuracy={accuracy:.4f}, aggregation={aggregation_wall:.4f}s",
            flush=True,
        )
    return model, history, time.perf_counter() - started_training


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mp-spdz", required=True, type=Path)
    parser.add_argument("--mnist", type=Path, default=Path("data/mnist.npz"))
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--clients", type=int, default=10)
    parser.add_argument("--examples-per-client", type=int, default=256)
    parser.add_argument("--test-examples", type=int, default=2_000)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--server-lr", type=float, default=1.0)
    parser.add_argument("--L", type=int, default=32)
    parser.add_argument("--protocol", choices=("semi", "shamir"), default="shamir")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--timeout", type=int, default=7200)
    parser.add_argument("--seed", type=int, default=20260805)
    parser.add_argument("--output", type=Path, default=Path("results/mnist-fl-median.csv"))
    args = parser.parse_args()
    if args.clients != 10:
        raise SystemExit("this experiment is fixed to ten clients for comparability")

    x_train_raw, y_train, x_test_raw, y_test = load_mnist(
        args.mnist, download=args.download
    )
    x_train = features(x_train_raw)
    x_test = features(x_test_raw[: args.test_examples])
    y_test = y_test[: args.test_examples]
    rng = np.random.default_rng(args.seed)
    selected = rng.permutation(len(x_train))[: args.clients * args.examples_per_client]
    client_data = []
    for client in range(args.clients):
        indices = selected[
            client * args.examples_per_client : (client + 1) * args.examples_per_client
        ]
        client_data.append((x_train[indices], y_train[indices]))
    initial = np.zeros(500, dtype=np.float64)

    all_history: list[dict[str, object]] = []
    totals = {}
    for mode in ("plaintext", "paper_mpc"):
        _, history, total = train(
            mode=mode,
            initial=initial,
            client_data=client_data,
            x_test=x_test,
            y_test=y_test,
            rounds=args.rounds,
            server_lr=args.server_lr,
            mp_spdz=args.mp_spdz.resolve(),
            L=args.L,
            protocol=args.protocol,
            batch_size=args.batch_size,
            timeout=args.timeout,
            seed=args.seed,
        )
        all_history.extend(history)
        totals[mode] = total

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = list(all_history[0]) + ["total_training_seconds"]
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in all_history:
            writer.writerow({**row, "total_training_seconds": totals[str(row["mode"])]})


if __name__ == "__main__":
    main()
