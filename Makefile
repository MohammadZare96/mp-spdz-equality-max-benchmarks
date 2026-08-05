.PHONY: test summarize plot plot-extensions median escg mnist network-profiles

test:
	python3 -m unittest discover -s tests -v

summarize:
	python3 benchmarks/summarize.py results/raw.csv results/summary.csv

plot:
	python3 benchmarks/plot_results.py results/summary.csv results/figures

plot-extensions:
	python3 benchmarks/plot_extensions.py results results/figures

median:
	python3 benchmarks/run_median_benchmarks.py --mp-spdz "$${MP_SPDZ:?set MP_SPDZ}"

escg:
	python3 benchmarks/run_escg_benchmarks.py --mp-spdz "$${MP_SPDZ:?set MP_SPDZ}"

mnist:
	python3 benchmarks/run_federated_mnist.py --mp-spdz "$${MP_SPDZ:?set MP_SPDZ}" --download

network-profiles:
	python3 benchmarks/network_profiles.py results/escg-raw.csv results/escg-network-profiles.csv
	python3 benchmarks/network_profiles.py results/median-vector-raw.csv results/median-network-profiles.csv --runtime-field mpc_runtime_seconds
