"""
Test that quickmark's MDParser.render() releases the GIL.

The strategy: if the GIL is properly released during render(), then a background
Python thread should be able to run concurrently while render() is executing.
If the GIL is NOT released, the background thread will be completely blocked
until render() finishes, and we'll observe a large wall-clock time for the
background thread's work that overlaps with render().

We use two independent measurements:
1. A background thread repeatedly increments a counter using pure Python
   (which requires the GIL). If the GIL is released by render(), the counter
   should advance significantly during the render call.
2. A background thread calls a simple C-extension-level no-op
   (time.time()) in a tight loop and records how many calls it makes
   during the render call.

We also do a control test: measure how long the background thread takes to
do its work when the GIL is NOT contested (render not running). Then we
compare to see if the render call is blocking it.
"""

import threading
import time
import sys

# We'll import quickmark once it's built
import quickmark


# Use a large enough markdown input that render() takes a meaningful amount of time
LARGE_MARKDOWN = "\n\n".join(
    [
        "# Heading {}\n\n".format(i)
        + "This is **bold** and *italic* text with `code` and [links](https://example.com).\n\n"
        + "- item 1\n- item 2\n- item 3\n\n"
        + "> A blockquote with some text in it.\n\n"
        + "```python\ndef hello():\n    print('world')\n```\n\n"
        + "| Col1 | Col2 | Col3 |\n|------|------|------|\n| a | b | c |\n| d | e | f |\n"
        for i in range(500)
    ]
)


def _gil_probe(stop_event, results):
    """Background thread function that counts how many iterations it can
    complete while the GIL is available to it."""
    count = 0
    # Pure-Python work that requires the GIL
    accumulator = 0
    while not stop_event.is_set():
        for _ in range(1000):
            accumulator += 1
        count += 1
    results["count"] = count
    results["accumulator"] = accumulator


def _calibrate_probe(duration=0.5):
    """Measure how many iterations the probe can do in `duration` seconds
    with no GIL contention."""
    stop = threading.Event()
    results = {}
    t = threading.Thread(target=_gil_probe, args=(stop, results))
    t.start()
    time.sleep(duration)
    stop.set()
    t.join()
    return results.get("count", 0), duration


def test_render_releases_gil():
    """Test that render() releases the GIL.

    We run the background probe thread, then call render() on a large input.
    If the GIL is released during render(), the background thread should make
    significant progress (close to its uncontested calibration rate).
    If the GIL is NOT released, the background thread will be completely
    starved and make ~0 progress during the render call.
    """
    # Step 1: calibrate - how many iterations can the probe do per second?
    cal_count, cal_duration = _calibrate_probe(duration=0.5)
    cal_rate = cal_count / cal_duration  # iterations per second

    # Step 2: set up the parser with plugins (like md_to_html does)
    parser = quickmark.MDParser("zero")
    parser.enable_many(
        [
            quickmark.Plugin(name="nl2br"),
            quickmark.Plugin(name="backticks"),
            quickmark.Plugin(name="escape"),
            quickmark.Plugin(name="emphasis"),
            quickmark.LinkExtensionPlugin(
                embed_third_party_content=False,
                open_links_in_new_tab=True,
            ),
            quickmark.ImageExtensionPlugin(),
            quickmark.Plugin(name="kagi_contact_info"),
            quickmark.Plugin(name="entity"),
            quickmark.Plugin(name="blockquote"),
            quickmark.Plugin(name="hr"),
            quickmark.Plugin(name="list"),
            quickmark.Plugin(name="heading"),
            quickmark.Plugin(name="paragraph"),
            quickmark.Plugin(name="html_inline"),
            quickmark.Plugin(name="html_block"),
            quickmark.Plugin(name="table"),
            quickmark.InlineMathExtensionPlugin(cache=True),
            quickmark.DisplayMathExtensionPlugin(cache=True),
        ]
    )

    # Step 3: start background probe thread
    stop_event = threading.Event()
    probe_results = {}
    probe_thread = threading.Thread(
        target=_gil_probe, args=(stop_event, probe_results)
    )
    probe_thread.start()

    # Step 4: call render() - this is the critical section
    t0 = time.monotonic()
    result = parser.render(LARGE_MARKDOWN)
    render_duration = time.monotonic() - t0

    # Stop the probe
    stop_event.set()
    probe_thread.join()

    # Step 5: analyze results
    probe_count = probe_results.get("count", 0)
    print(f"\n  Render duration:    {render_duration:.4f}s")
    print(f"  Calibration rate:   {cal_rate:.0f} iter/s")
    print(f"  Probe iterations:   {probe_count}")
    print(f"  Expected (no GIL block): ~{cal_rate * render_duration:.0f}")
    print(f"  Render output length: {len(result)} chars")
    assert len(result) > 0, "render() should produce some HTML"

    # The probe should have completed at least 30% of what it would have
    # done if there were zero contention.  If the GIL is held by render(),
    # the probe will get almost nothing (close to 0).
    expected = cal_rate * render_duration
    ratio = probe_count / expected if expected > 0 else 0
    print(f"  Contention ratio:   {ratio:.2%}")

    assert ratio > 0.30, (
        f"GIL appears to be held during render(). "
        f"Background probe completed {probe_count} iterations, "
        f"expected ~{expected:.0f} (ratio={ratio:.2%}). "
        f"If the GIL were released, the background thread should have "
        f"run concurrently."
    )


def test_concurrent_renders():
    """Test that multiple threads can render concurrently.

    If the GIL is released during render(), N threads should finish in
    roughly the same wall-clock time as 1 thread (linear speedup).
    If the GIL is NOT released, N threads should take ~N times as long.
    """
    parser = quickmark.MDParser("zero")
    parser.enable_many(
        [
            quickmark.Plugin(name="nl2br"),
            quickmark.Plugin(name="backticks"),
            quickmark.Plugin(name="escape"),
            quickmark.Plugin(name="emphasis"),
            quickmark.LinkExtensionPlugin(
                embed_third_party_content=False,
                open_links_in_new_tab=True,
            ),
            quickmark.ImageExtensionPlugin(),
            quickmark.Plugin(name="kagi_contact_info"),
            quickmark.Plugin(name="entity"),
            quickmark.Plugin(name="blockquote"),
            quickmark.Plugin(name="hr"),
            quickmark.Plugin(name="list"),
            quickmark.Plugin(name="heading"),
            quickmark.Plugin(name="paragraph"),
            quickmark.Plugin(name="html_inline"),
            quickmark.Plugin(name="html_block"),
            quickmark.Plugin(name="table"),
            quickmark.InlineMathExtensionPlugin(cache=True),
            quickmark.DisplayMathExtensionPlugin(cache=True),
        ]
    )

    NUM_THREADS = 4

    def render_in_thread(results, idx):
        t0 = time.monotonic()
        html = parser.render(LARGE_MARKDOWN)
        elapsed = time.monotonic() - t0
        results[idx] = (elapsed, len(html))

    # Warm-up
    parser.render("# warmup")

    # Single-threaded baseline
    results_single = {}
    t0 = time.monotonic()
    render_in_thread(results_single, 0)
    single_wall = time.monotonic() - t0
    single_render = results_single[0][0]

    # Multi-threaded
    results_multi = {}
    threads = []
    t0 = time.monotonic()
    for i in range(NUM_THREADS):
        t = threading.Thread(target=render_in_thread, args=(results_multi, i))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    multi_wall = time.monotonic() - t0

    # Compute speedup
    speedup = (single_render * NUM_THREADS) / multi_wall if multi_wall > 0 else 0
    print(f"\n  Single render time:  {single_render:.4f}s")
    print(f"  {NUM_THREADS}x single serial: {single_render * NUM_THREADS:.4f}s")
    print(f"  {NUM_THREADS} threads wall:   {multi_wall:.4f}s")
    print(f"  Speedup:            {speedup:.2f}x")

    # If GIL is released, we should see at least 1.5x speedup
    # (not perfect linear due to overhead, but definitely > 1x)
    # If GIL is held, speedup will be ~1.0x (serialized)
    assert speedup > 1.5, (
        f"Multiple render threads are not achieving concurrency. "
        f"Speedup is {speedup:.2f}x with {NUM_THREADS} threads "
        f"(expected > 1.5x if GIL is released). "
        f"Single render: {single_render:.4f}s, "
        f"Multi-thread wall: {multi_wall:.4f}s."
    )


if __name__ == "__main__":
    print("=" * 60)
    print("Test 1: GIL probe test")
    print("=" * 60)
    try:
        test_render_releases_gil()
        print("PASSED")
    except AssertionError as e:
        print(f"FAILED: {e}")
        sys.exit(1)

    print()
    print("=" * 60)
    print("Test 2: Concurrent renders speedup test")
    print("=" * 60)
    try:
        test_concurrent_renders()
        print("PASSED")
    except AssertionError as e:
        print(f"FAILED: {e}")
        sys.exit(1)
