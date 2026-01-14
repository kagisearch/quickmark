//! Plugin to parse footnote references
//!
//! ```rust
//! let parser = &mut quickmark::MarkdownIt::new();
//! quickmark::plugins::cmark::add(parser);
//! quickmark::plugins::footnote::references::add(parser);
//! quickmark::plugins::footnote::definitions::add(parser);
//! let root = parser.parse("[^label]\n\n[^label]: This is a footnote");
//! let mut names = vec![];
//! root.walk(|node,_| { names.push(node.name()); });
//! assert_eq!(names, vec![
//! "quickmark::mdparser::core::root::Root",
//! "quickmark::plugins::cmark::block::paragraph::Paragraph",
//! "quickmark::plugins::footnote::references::FootnoteReference",
//! "quickmark::plugins::footnote::definitions::FootnoteDefinition",
//! "quickmark::plugins::cmark::block::paragraph::Paragraph",
//! "quickmark::mdparser::inline::builtin::skip_text::Text"
//! ]);
//! ```
use crate::mdparser::inline::{InlineRule, InlineState};
use crate::{MarkdownIt, Node, NodeValue, Renderer};

use crate::plugins::footnote::FootnoteMap;

/// Add the footnote reference parsing to the markdown parser
pub fn add(md: &mut MarkdownIt) {
    // insert this rule into inline subparser
    md.inline.add_rule::<FootnoteReferenceScanner>();
}

#[derive(Debug)]
/// AST node for footnote reference
pub struct FootnoteReference {
    pub label: Option<String>,
    pub ref_id: usize,
    pub def_id: usize,
}

impl NodeValue for FootnoteReference {
    fn render(&self, node: &Node, fmt: &mut dyn Renderer) {
        let mut attrs = node.attrs.clone();
        attrs.push(("class", "footnote-ref".into()));

        fmt.open("sup", &attrs);
        fmt.open(
            "a",
            &[
                ("href", format!("#fn{}", self.def_id)),
                ("id", format!("fnref{}", self.ref_id)),
            ],
        );
        fmt.text(&format!("[{}]", self.def_id));
        fmt.close("a");
        fmt.close("sup");
    }
}

// This is an extension for the inline subparser.
struct FootnoteReferenceScanner;

impl InlineRule for FootnoteReferenceScanner {
    const MARKER: char = '[';

    fn run(state: &mut InlineState) -> Option<(Node, usize)> {
        let mut chars = state.src[state.pos..state.pos_max].chars();

        // check line starts with the correct syntax
        let Some('[') = chars.next() else {
            return None;
        };
        let Some('^') = chars.next() else {
            return None;
        };

        // gather the label
        let mut label = String::new();
        // The labels in footnote references may not contain spaces, tabs, or newlines.
        // Backslash escapes form part of the label and do not escape anything
        loop {
            match chars.next() {
                None => return None,
                Some(']') => {
                    break;
                }
                Some(' ') => return None,
                Some(c) => label.push(c),
            }
        }
        if label.is_empty() {
            return None;
        }

        let definitions = state.root_ext.get_or_insert_default::<FootnoteMap>();
        let (def_id, ref_id) = match definitions.add_ref(&label) {
            Some(value) => value,
            // no definition found so this is not a footnote reference
            None => return None,
        };

        let length = label.len() + 3; // 3 for '[^' and ']'

        // return new node and length of this structure
        Some((
            Node::new(FootnoteReference {
                label: Some(label),
                ref_id,
                def_id,
            }),
            length,
        ))
    }
}
