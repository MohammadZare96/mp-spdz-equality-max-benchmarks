# MP-SPDZ Equality, Max, Median, and Extended SCG Benchmarks

Reproducible MP-SPDZ implementation of the equality test, multi-input maximum,
Extended SCG, and median constructions from *Beyond Yao's Millionaires: Secure
Multi-Party Computation of Non-Polynomial Functions*, plus a small federated
MNIST experiment using the paper-compatible coordinate-wise median.


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
| Coordinate-wise Median runtime | `K=N=10`, `D in {100,1000,10000}` |
| Extended SCG runtime vs. scale | `L=32`, `K=N in {2,4,8,10,20,30,40,50}` |
| Federated MNIST | 10 clients, 500 model parameters, 3 rounds, plaintext vs. secure Median |
| LAN/WAN sensitivity | trace-based estimates at 1 ms/1 Gbps and 50 ms/100 Mbps |

The request contained the dimensions `100,1000,1000`; the second repeated
`1000` is interpreted as `10000` so the sweep spans three orders of magnitude.
Override `--dimensions` if the duplicate was intentional.

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
- Extended SCG applies the same oblivious choice to the encoded value and its
  secret-shared source index, returning the maximum and its index together.
- Median computes each unordered pairwise SCI once, derives the reverse bit
  from distinctness, counts ranks, and selects the candidate whose number of
  greater-or-equal inputs is `K/2`. With even `K=10`, this is the upper median.

The paper's Median rank test assumes distinct inputs. Random benchmarks sample
distinct values per coordinate. The federated experiment uses a monotone
fixed-point quantizer and the client index only as a deterministic tie-breaker;
this preserves coordinate-wise ordering while meeting that precondition.

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

## Run Median, Extended SCG, and federated MNIST

```bash
# Paper-compatible coordinate-wise Median with ten Shamir parties.
python3 benchmarks/run_median_benchmarks.py \
  --mp-spdz /opt/MP-SPDZ \
  --dimensions 100 1000 10000 \
  --clients 10 --parties 10 --L 16 --protocol shamir \
  --repetitions 3 --output results/median-vector-raw.csv

# Extended SCG returns both the maximum and its secret index.
python3 benchmarks/run_escg_benchmarks.py \
  --mp-spdz /opt/MP-SPDZ \
  --sizes 2 4 8 10 20 30 40 50 \
  --L 32 --protocol semi --repetitions 3 \
  --output results/escg-raw.csv

# Actual MNIST data, a 7x7 softmax classifier (500 parameters), ten clients.
python3 benchmarks/run_federated_mnist.py \
  --mp-spdz /opt/MP-SPDZ --download \
  --clients 10 --examples-per-client 256 --test-examples 2000 \
  --rounds 3 --L 32 --protocol shamir \
  --output results/mnist-fl-median.csv

python3 benchmarks/network_profiles.py \
  results/escg-raw.csv results/escg-network-profiles.csv
python3 benchmarks/summarize_extensions.py results
python3 benchmarks/plot_extensions.py results results/figures
```

The checked-in measurements are correctness-gated. Median used Shamir to match
the paper's honest-majority model. Extended SCG used `semi` so the full sweep,
including `N=2`, stays on one backend. Its `N=50` point used batch size 400
because batch size 500 exceeded the benchmark host's memory; all smaller points
used 500 and every revealed value/index pair was verified.

### Observed extension results

| Experiment | Small point | Large point |
| --- | ---: | ---: |
| Secure Median runtime | 0.407 s at D=100 | 31.813 s at D=10,000 |
| Secure Median global communication | 77.4 MB | 7.742 GB |
| Extended SCG runtime | 0.00844 s at N=2 | 48.122 s at N=50 |
| Extended SCG global communication | 0.214 MB | 12.830 GB |

The hypothesis that secure Median has “no overhead” is **not supported by these
measurements**. Compared with vectorized NumPy, the median runtime ratio is
roughly 59,500–80,600x. In the MNIST run, both aggregators produced the same
test-accuracy path (36.85%, 43.65%, 48.60%), but secure aggregation added
2.65–3.07 seconds of reported MPC runtime and 859.752 MB per round. The useful
result is functional equivalence of the trained trajectory, not negligible
absolute overhead.

## LAN and WAN conditions

`scripts/netem_profile.sh` can apply actual Linux `tc netem` profiles on a host
with `CAP_NET_ADMIN`:

```bash
sudo ./scripts/netem_profile.sh apply LAN lo   # 1 ms, 1 Gbps
sudo ./scripts/netem_profile.sh apply WAN lo   # 50 ms, 100 Mbps
sudo ./scripts/netem_profile.sh clear lo
```

The checked-in `escg-network-*.csv` files use a clearly labeled trace model
because this container does not grant network-administration capability:

`estimated = measured loopback runtime + rounds * latency + bytes / bandwidth`

This is a sensitivity estimate, not a packet-level netem measurement. For N=50
the median estimate is 198.6 s on LAN and 3465.8 s on WAN; high round count,
not just bandwidth, dominates the WAN result.

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
