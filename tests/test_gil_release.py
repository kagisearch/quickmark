"""Check output consistency when sharing a parser across threads.

Rust unit tests (`cargo test --lib gil_tests`) cover GIL release.
Threaded rendering throughput is measured in benchmarks/bench_threads.py.
"""

from concurrent.futures import ThreadPoolExecutor

import quickmark

# Exercise multiple block and inline rules while sharing the parser.
LARGE_MARKDOWN = "\n\n".join(
    [
        f"# Heading {i}\n\n"
        "This is **bold** and *italic* text with `code` and [links](https://example.com).\n\n"
        "- item 1\n- item 2\n- item 3\n\n"
        "> A blockquote with some text in it.\n\n"
        "```python\ndef hello():\n    print('world')\n```\n\n"
        "| Col1 | Col2 | Col3 |\n|------|------|------|\n| a | b | c |\n| d | e | f |\n"
        for i in range(500)
    ]
)


def test_concurrent_renders():
    """A shared parser must return the same HTML as serial rendering."""
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

    documents = [f"# Render {i}\n\n{LARGE_MARKDOWN}" for i in range(8)]
    expected = [parser.render(document) for document in documents]

    with ThreadPoolExecutor(max_workers=4) as pool:
        # Consuming map retrieves every result and propagates worker exceptions.
        actual = list(pool.map(parser.render, documents))

    assert actual == expected
