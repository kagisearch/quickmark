//! A [markdown_it] plugin for parsing Github Flavoured Markdown
//!
//! ```rust
//! let parser = &mut quickmark::MarkdownIt::new();
//! quickmark::plugins::extra::gh_flavored_md::add(parser);
//! let root = parser.parse("https://github.github.com/gfm");
//! assert_eq!(root.render(), "<p><a href=\"https://github.github.com/gfm\">https://github.github.com/gfm</a></p>\n");
//! ```
use crate::mdparser::inline::builtin::InlineParserRule;
use crate::plugins::html::html_block::HtmlBlock;
use crate::plugins::html::html_inline::HtmlInline;
use crate::{mdparser::core::CoreRule, MarkdownIt, Node};
use regex::Regex;

pub const GITHUB_PLUGIN_NAMES: [&str; 22] = [
    "newline",
    "escape",
    "backticks",
    "emphasis",
    "link",
    "image",
    "autolink_ext",
    "entity",
    "code",
    "fence",
    "blockquote",
    "hr",
    "list",
    "reference",
    "heading",
    "lheading",
    "paragraph",
    "table",
    "strikethrough",
    "html_block",
    "html_inline",
    "tasklist",
];

/// Add the GFM plugin to the parser
pub fn add(md: &mut MarkdownIt) {
    crate::plugins::cmark::add(md);
    crate::plugins::extra::tables::add(md);
    crate::plugins::extra::strikethrough::add(md);
    crate::plugins::html::add(md);
    md.add_rule::<TagFilter>().after::<InlineParserRule>();
    crate::plugins::extra::tasklist::add_disabled(md);
    crate::plugins::autolinks::add(md);
}

/// Add the GFM plugin to the parser, plus heading anchors
pub fn add_with_anchors(md: &mut MarkdownIt) {
    add(md);
    crate::plugins::extra::heading_anchors::add(md);
}

/// Implement the Disallowed Raw HTML (tagfilter) rule
struct TagFilter;
impl CoreRule for TagFilter {
    fn run(root: &mut Node, _md: &MarkdownIt) {
        let regex = Regex::new(
            r#"<(?i)(iframe|noembed|noframes|plaintext|script|style|title|textarea|xmp)"#,
        )
        .unwrap();
        root.walk_mut(|node, _| {
            if let Some(value) = node.cast_mut::<HtmlBlock>() {
                value.content = regex.replace_all(&value.content, "&lt;$1").to_string();
            }
            if let Some(value) = node.cast_mut::<HtmlInline>() {
                value.content = regex.replace_all(&value.content, "&lt;$1").to_string();
            }
        });
    }
}
