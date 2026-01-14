# quickmark

The library is based on the architecture of [markdown-it-py](https://github.com/ExecutableBookProject/markdown-it-py), making it easy to port their plugins.

# Dev Dependencies

You can run `make install_toolchain` (rust+cargo+uv)

Build with:

```bash
# Installs toolchain (cargo + uv)
make install_toolchain

# Builds entire project
make build
# OPTIONAL: Install built package in local python env
uv run maturin develop --release
```

**NOTE:** If using conda/mamba on macos, builds can break. [Reinstalling mamba helps.](https://github.com/PyO3/pyo3/issues/1554)


# Usage (Rust)

```rust
let parser = &mut crate::MarkdownIt::new();
crate::plugins::cmark::add(parser);
crate::plugins::extra::add(parser);

let ast  = parser.parse("Hello **world**!");
let html = ast.render();

print!("{html}");
// prints "<p>Hello <strong>world</strong>!</p>"
```

# Usage (python)

If you built the python package, it should be installed as `quickmark` in the local python environment. Syntax looks like that of `markdown-it-py`:

```python
from quickmark import MDParser

md = MDParser("commonmark").enable("table")
md.render("# Hello, world!")
# '<h1>Hello, world!</h1>\n'
```

- `MarkdownIt("zero")` will not enable any plugins.

- `MarkdownIt("commonmark")` for all CommonMark plugins.

- `MarkdownIt("gfm")` for CommonMark + GitHub Flavoured Markdown plugins.

### Python CLI


A cli is in `python/quickmark/cli.py`, which can be used like this:

```bash
# replace - with filename to read from a file
# see `quickmark --help` for more
echo "# Hello, world!" | quickmark html -
# <h1>Hello, world!</h1>

echo "# Hello, world!" | quickmark ast -
# <root>
#   <heading>
#     <text>
```


### Python AST walking

`markdown-it.rs` does not generate a token stream, but instead directly generates a `Node` tree.
This is similar to the `markdown-it-py`'s `SyntaxTreeNode` class, although the API is not identical.
(source mapping is also provided by byte-offset, rather than line only)

```python
md = (
  MDParser("commonmark")
  .enable("table")
  .enable_many(["linkify", "strikethrough"])
)
node = md.tree("# Hello, world!")
print(node.walk())
# [Node(root), Node(heading), Node(text)]
print(node.pretty(srcmap=True, meta=True))
# <root srcmap="0:15">
#   <heading srcmap="0:15">
#     level: 1
#     <text srcmap="2:15">
#       content: Hello, world!
```

**Note:** Attributes of the `Node` class, such as `Node.attrs`, return a **copy** of the underlying data, and so mutating it will not affect what is stored on the node, e.g.

```python
from quickmark import Node
node = Node("name")
# don't do this!
node.attrs["key"] = "value"
print(node.attrs) # {}
# do this instead (Python 3.9+)
node.attrs = node.attrs | {"key": "value"}
print(node.attrs) # {"key": "value"}
# Node.children is only a shallow copy though, so this is fine
child = Node("child")
node.children = [child]
node.children[0].name = "other"
print(child.name) # "other"
```

### WASM Build

There is a webassembly build in the example demos.

# Extending

For a guide on how to extend it, see `examples` folder.

For translating markdown-it plugins to rust, here are some useful notes:

- `state.bMarks[startLine] + state.tShift[startLine]` is equivalent to `state.line_offsets[line].first_nonspace`
- `state.eMarks[startLine]` is equivalent to `state.line_offsets[line].line_end`
- `state.sCount[line]` is equivalent to `state.line_offsets[line].indent_nonspace`
- `state.sCount[line] - state.blkIndent` is equivalent to `state.line_indent(state.line)`


## Plugins

All syntax rules in `markdown-it.rs` are implemented as plugins.
Plugins can be added to the parser by calling `enable` or `enable_many` with the name of the plugin.
The following plugins are currently supported:

CommonMark Blocks:

- `blockquote`: Block quotes with `>`
- `code`: Indented code blocks
- `fence`: Backtick code blocks
- `heading`: `#` ATX headings
- `hr`: `---` horizontal rules
- `lheading`: `---` underline setext headings
- `list`: `*` unordered lists and `1.` ordered lists
- `paragraph`: Paragraphs
- `reference`: Link reference definitions `[id]: src "title"`

CommonMark Inlines:

- `autolink`: `<http://example.com>`
- `backticks`: `` `code` ``
- `emphasis`: `_emphasis_`, `*emphasis*`, `**strong**`, `__strong__`
- `entity`: `&amp;`
- `escape`: backslash escaping `\`
- `image`: `![alt](src "title")`
- `link`: `[text](src "title")`, `[text][id]`, `[text]`
- `newline`: hard line breaks
- `html_block`: HTML blocks
- `html_inline`: HTML inline
- `sourcepos`: Add source mapping to rendered HTML, looks like this: `<stuff data-sourcepos="1:1-2:3">`, i.e. `line:col-line:col`
- `replacements`: Typographic replacements, like `--` to `—`
- `smartquotes`: Smart quotes, like `"` to `“`
- `linkify`: Automatically linkify URLs with <https://crates.io/crates/linkify> (note currently this only matches URLs with a scheme, e.g. `https://example.com`)
- `heading_anchors`: Add heading anchors, with defaults like GitHub
- `front_matter`: YAML front matter
- `footnote`: Pandoc-style footnotes (see <https://pandoc.org/MANUAL.html#footnotes>)

GitHub Flavoured Markdown (<https://github.github.com/gfm>):

- `table`:

  ```markdown
  | foo | bar |
  | --- | --- |
  | baz | bim |
  ```
- `strikethrough`: `~~strikethrough~~`
- `tasklist`: `- [x] tasklist item`
- `autolink_ext`: Extended autolink detection with "bare URLs" like `https://example.com` and `www.example.com`
- `tagfilter`: HTML tag filtering, e.g. `<script>` tags are removed


