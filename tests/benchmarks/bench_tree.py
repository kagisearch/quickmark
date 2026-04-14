from pathlib import Path

import pytest


@pytest.fixture
def spec_text():
    return Path(__file__).parent.joinpath("fixtures", "spec.md").read_text()


@pytest.mark.benchmark(group="tree")
def test_markdown_it_py(benchmark, spec_text):
    import markdown_it
    from markdown_it.tree import SyntaxTreeNode

    parser = markdown_it.MarkdownIt("commonmark")
    benchmark.extra_info["version"] = markdown_it.__version__

    def _to_tree(text):
        tokens = parser.parse(text)
        return SyntaxTreeNode(tokens)

    benchmark(parser.parse, spec_text)


@pytest.mark.benchmark(group="tree")
def test_quickmark(benchmark, spec_text):
    import quickmark

    parser = quickmark.MarkdownIt("commonmark")
    benchmark.extra_info["version"] = quickmark.__version__
    benchmark(parser.tree, spec_text)
