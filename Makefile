.PHONY: test summarize plot

test:
	python3 -m unittest discover -s tests -v

summarize:
	python3 benchmarks/summarize.py results/raw.csv results/summary.csv

plot:
	python3 benchmarks/plot_results.py results/summary.csv results/figures
