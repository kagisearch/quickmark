use crate::mdparser::inline::{InlineRule, InlineState};
use crate::mdparser::preprocess::INLINE_MATH_DOLLAR_REGEX;
use crate::plugin_config::InlineMathExtensionPlugin;
use crate::plugins::kagi_plugins::math::{math_render, math_render_cached};
use crate::{MarkdownIt, Node, NodeValue, Renderer};
use html_escape::decode_html_entities;

#[derive(Debug)]
pub struct InlineMath {
    pub math: String,
    pub cache: bool,
}

impl NodeValue for InlineMath {
    fn render(&self, _: &Node, fmt: &mut dyn Renderer) {
        let math_render_func = if self.cache {
            math_render_cached
        } else {
            math_render
        };
        fmt.text_raw(&math_render_func(self.math.clone(), false))
    }
}

struct MathInlineScanner;

impl InlineRule for MathInlineScanner {
    const MARKER: char = '$';

    fn run(state: &mut InlineState) -> Option<(Node, usize)> {
        let input = &state.src[state.pos..state.pos_max];
        if !input.starts_with(Self::MARKER) {
            return None;
        }
        let config = state.md.ext.get::<InlineMathExtensionPlugin>().unwrap();

        let valid_preceeding_chars = ['*', '(', '：'];
        let preceeding_char = state
            .src
            .get(..state.pos)
            .and_then(|s| s.chars().rev().next());
        if let Some(c) = preceeding_char {
            if !(valid_preceeding_chars.contains(&c) || c.is_whitespace()) {
                return None;
            }
        }

        if let Ok(Some(caps)) = INLINE_MATH_DOLLAR_REGEX.captures(input) {
            let complete_match = &caps[0];
            let math = caps.name("math")?.as_str();
            Some((
                Node::new(InlineMath {
                    math: decode_html_entities(math).to_string(),
                    cache: config.cache,
                }),
                complete_match.len(),
            ))
        } else {
            None
        }
    }
}

pub fn add(md: &mut MarkdownIt, config: InlineMathExtensionPlugin) {
    md.ext.insert(config);
    md.inline.add_rule::<MathInlineScanner>();
}
