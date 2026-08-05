# MP-SPDZ Equality and Max Benchmarks

Reproducible MP-SPDZ implementation of the equality test in Section 3.2 and
the multi-input maximum construction in Sections 3.3-3.5 of *Beyond Yao's
Millionaires: Secure Multi-Party Computation of Non-Polynomial Functions*.


## Live benchmark dashboard

The verified interactive dashboard is deployed at:

https://mp-spdz-benchmarks.mohre1918.chatgpt.site

The repository includes all 120 correctness-checked raw runs in
`results/raw.csv`, the 24-point median/IQR table in `results/summary.csv`,
and the dashboard source under `site/`.

The repository generates runtime and communication measurements for exactly
these experiment families:

| Sweep | Parameters |
| --- | --- |
| Equality runtime and communication vs. bit length | `K=N=8`, `L in {8,16,32,64}` |
| Max runtime and communication vs. bit length | `K=N=8`, `L in {8,16,32,64}` |
| Equality runtime and communication vs. scale | `L=32`, `K=N in {2,4,8,10,20,30,40,50}` |
| Max runtime and communication vs. scale | `L=32`, `K=N in {2,4,8,10,20,30,40,50}` |

Here `K` is the number of private values in the Max experiment and `N` is the
number of MPC parties. Equality always compares two private values, but keeps
`K` in the experiment coordinates so it shares the same `K=N` scale points.

## Protocol implementation

- Equality computes `(a-b)^(q-1)` in the prime field. It preserves the paper's
  output convention: zero means equal and one means unequal.
- Max uses the paper's partition and 0-coded vectors. Each input owner creates
  these vectors locally and secret-shares them as private MP-SPDZ inputs.
- Each SCG computes the product of partition/0-code differences, applies the
  same Fermat zero indicator, and obliviously selects both encoded vectors.
- A balanced SCG tree returns the maximum without opening intermediate values.

The supplied values have exactly `L` bits. This is important because the
paper's "random string of length unequal to i" rule assumes that an `i`-bit
prefix also has numerical bit length `i`; leading-zero inputs violate that
assumption. The runner samples inputs from `[2^(L-1), q)`.

The field primes are the largest primes below `2^L`: 251, 65521, 4294967291,
and 18446744073709551557. Consequently `L = ceil(log2(q))`, as assumed by the
paper, and the Fermat exponent is exactly `q-1`.

## Setup

The setup script pins MP-SPDZ to commit
`9d809599ea6ce627216a389ca7d984fbb75d0cb9`:

```bash
./scripts/setup_mp_spdz.sh /opt/MP-SPDZ
```

MP-SPDZ requires its normal compiler dependencies. See the upstream setup
instructions if the build reports a missing system package.

## Run the complete matrix

```bash
python3 benchmarks/run_benchmarks.py \
  --mp-spdz /opt/MP-SPDZ \
  --protocol semi \
  --batch-size 500 \
  --repetitions 5 \
  --output results/raw.csv

python3 benchmarks/summarize.py results/raw.csv results/summary.csv
python3 benchmarks/plot_results.py results/summary.csv results/figures
```

`semi` is the default because it supports the complete requested matrix,
including `N=2`, under one MP-SPDZ backend. It provides semi-honest
computational security and therefore does **not** reproduce the paper's
information-theoretic security model.

For the paper's honest-majority Shamir model, use:

```bash
python3 benchmarks/run_benchmarks.py \
  --mp-spdz /opt/MP-SPDZ \
  --protocol shamir \
  --repetitions 5 \
  --output results/shamir-raw.csv
```

MP-SPDZ Shamir requires at least three parties, so the runner explicitly skips
the `N=2` points. Do not mix the `semi/N=2` point into a Shamir curve without
labeling the backend change.

Useful filters:

```bash
# Only the fixed K=N=8, varying-L Max runs
python3 benchmarks/run_benchmarks.py --mp-spdz /opt/MP-SPDZ \
  --operation max --sweep vary_L

# Compile beforehand, then run without recompilation
python3 benchmarks/run_benchmarks.py --mp-spdz /opt/MP-SPDZ --no-compile
```

## Metrics

Each repetition is correctness-checked before it is appended to the raw CSV.
Runtime is the maximum `Time = ...` reported across parties. Communication is
MP-SPDZ's `Global data sent`, summed across all parties; the maximum per-party
communication and round count are retained as diagnostic columns.

The preprocessing batch size defaults to 500. This bounds peak memory for the
requested 40- and 50-party local runs, and the value is recorded in every raw
row for reproducibility.

`summarize.py` reports the median and interquartile range for runtime and global
communication. `plot_results.py` creates the four requested comparisons as
both publication-ready PDF and 220-DPI PNG files. Equality and Max are separate
series, the line is the median, and the shaded band is the interquartile range.

Install the plotting dependency with `python3 -m pip install -r requirements.txt`.

This is research benchmark code, not an audited cryptographic library.

## Validation

```bash
make test
```

The tests cover the paper's partition-vector example, the 0-code rule, the
comparison zero criterion for every pair of 8-bit field inputs, the exact
24-case experiment matrix, and MP-SPDZ metric parsing.
