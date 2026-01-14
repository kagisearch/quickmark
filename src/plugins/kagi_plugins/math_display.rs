use crate::mdparser::inline::{InlineRule, InlineState};
use crate::mdparser::preprocess::DISPLAY_MATH_DOLLAR_REGEX;
use crate::plugin_config::DisplayMathExtensionPlugin;
use crate::plugins::kagi_plugins::math::{math_render, math_render_cached};
use crate::{MarkdownIt, Node, NodeValue, Renderer};
use html_escape::decode_html_entities;

const OPEN_DISPLAY_MATH: &str = "$$";

#[derive(Debug)]
pub struct DisplayMath {
    pub math: String,
    pub cache: bool,
}

impl NodeValue for DisplayMath {
    fn render(&self, _: &Node, fmt: &mut dyn Renderer) {
        let math_render_func = if self.cache {
            math_render_cached
        } else {
            math_render
        };
        fmt.text_raw(&math_render_func(self.math.clone(), true))
    }
}

struct MathDisplayScanner;

impl InlineRule for MathDisplayScanner {
    const MARKER: char = '$';

    fn run(state: &mut InlineState) -> Option<(Node, usize)> {
        let input = &state.src[state.pos..state.pos_max];
        if !input.starts_with(OPEN_DISPLAY_MATH) {
            return None;
        }
        let config = state.md.ext.get::<DisplayMathExtensionPlugin>().unwrap();

        let preceeding_char = state
            .src
            .get(..state.pos)
            .and_then(|s| s.chars().rev().next());
        if let Some(c) = preceeding_char {
            if c == '\\' {
                return None;
            }
        }

        if let Ok(Some(caps)) = DISPLAY_MATH_DOLLAR_REGEX.captures(input) {
            let complete_match = &caps[0];
            let math = caps.name("math")?.as_str();
            Some((
                Node::new(DisplayMath {
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

pub fn add(md: &mut MarkdownIt, config: DisplayMathExtensionPlugin) {
    md.ext.insert(config);
    md.inline.add_rule::<MathDisplayScanner>();
}
