use crate::mdparser::inline::{InlineRule, InlineState};
use crate::{MarkdownIt, Node, NodeValue, Renderer};

#[derive(Debug)]
pub struct InlineNL2BR;

impl NodeValue for InlineNL2BR {
    fn render(&self, _: &Node, fmt: &mut dyn Renderer) {
        fmt.self_close("br", &[]);
        fmt.cr();
    }
}

struct NL2BRInlineScanner;

impl InlineRule for NL2BRInlineScanner {
    const MARKER: char = '\n';

    fn run(state: &mut InlineState) -> Option<(Node, usize)> {
        let input = &state.src[state.pos..state.pos_max];
        if !input.starts_with(Self::MARKER) {
            return None;
        }

        Some((Node::new(InlineNL2BR), 1))
    }
}

pub fn add(md: &mut MarkdownIt) {
    md.inline.add_rule::<NL2BRInlineScanner>();
}
