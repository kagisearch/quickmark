"""Measure shared-parser throughput with 1, 2, and 4 worker threads.

Run after building the release extension:
    uv run python tests/benchmarks/bench_threads.py

Each worker count renders the same total number of documents. Timings exclude
pool startup and warmup; speedup is reported without a pass/fail threshold.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from itertools import repeat
from pathlib import Path
from statistics import median
from threading import Barrier
from time import perf_counter

from quickmark import MDParser


def measure(parser, source, expected, workers, renders, rounds):
    ready = Barrier(workers)

    def warm_worker():
        parser.render(source)
        # Keep each worker occupied until all have warmed their thread-local state.
        ready.wait(timeout=30)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        warmups = [pool.submit(warm_worker) for _ in range(workers)]
        for future in warmups:
            future.result()

        samples = []
        for _ in range(rounds):
            start = perf_counter()
            outputs = list(pool.map(parser.render, repeat(source, renders)))
            samples.append(perf_counter() - start)
            if any(output != expected for output in outputs):
                raise RuntimeError("Threaded output differs from serial output")

    return median(samples)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).with_name("test-file.md"),
        help="Markdown input (default: the existing benchmark fixture)",
    )
    cli.add_argument("--config", choices=("kagi", "commonmark", "gfm"), default="kagi")
    cli.add_argument("--renders", type=int, default=128, help="renders per round")
    cli.add_argument("--rounds", type=int, default=5, help="rounds per worker count")
    args = cli.parse_args()
    if args.renders < 1 or args.rounds < 1:
        cli.error("--renders and --rounds must be positive")

    source = args.input.read_text(encoding="utf-8")
    parser = MDParser(args.config)
    expected = parser.render(source)

    print(f"Input: {args.input} ({len(source.encode('utf-8')):,} bytes)")
    print(
        f"Parser: {args.config}; {args.renders} renders per round; "
        f"median of {args.rounds} rounds"
    )
    print(f"{'Workers':>7} {'Median (s)':>12} {'Renders/s':>12} {'Speedup':>9}")
    baseline = None
    for workers in (1, 2, 4):
        elapsed = measure(parser, source, expected, workers, args.renders, args.rounds)
        if baseline is None:
            baseline = elapsed
        print(
            f"{workers:>7} {elapsed:>12.4f} "
            f"{args.renders / elapsed:>12.1f} {baseline / elapsed:>8.2f}x"
        )


if __name__ == "__main__":
    main()
