//! Images
//!
//! `![image](<src> "title")`
//!
//! <https://spec.commonmark.org/0.30/#images>
use crate::mdparser::inline::{InlineRule, InlineState};
use crate::plugins::kagi_plugins::link::LINK_MD_PATTERN;
use crate::{MarkdownIt, Node, NodeValue, Renderer};
use html_escape::decode_html_entities;

#[derive(Debug)]
pub struct Image {
    pub url: Option<String>,
    pub title: String,
}

impl NodeValue for Image {
    fn render(&self, node: &Node, fmt: &mut dyn Renderer) {
        let mut attrs = node.attrs.clone();

        if self.url.is_none() {
            fmt.text(&self.title);
            return;
        }
        let url = self.url.as_ref().unwrap();

        attrs.push(("alt", self.title.clone()));
        attrs.push(("src", url.clone()));

        fmt.self_close("img", &attrs);
    }
}

struct ImageScanner;

impl InlineRule for ImageScanner {
    const MARKER: char = '!';

    fn run(state: &mut InlineState) -> Option<(Node, usize)> {
        let input = &state.src[state.pos..state.pos_max];
        if !input.starts_with("![") {
            return None;
        }
        // Match the `[...](...)` portion starting right after the `!`. LINK_MD_PATTERN
        // is anchored with `^`, so we pass `&input[1..]` to align the anchor with the
        // `[`. `!` is ASCII, so slicing by 1 is safe.
        if let Some(caps) = LINK_MD_PATTERN.captures(&input[1..]) {
            let complete_match = &caps[0];
            let link_text = caps.name("link_text").map(|m| m.as_str().to_string())?;
            let link_text = decode_html_entities(&link_text).to_string();
            let url = caps
                .name("url")
                .map(|m| decode_html_entities(m.as_str()).to_string());

            Some((
                Node::new(Image {url, title: link_text}),
                // NOTE(Rehan): + 1 for exclamation mark
                // trim end to not replace trailing newline
                1 + complete_match.trim_end().len(),
            ))
        } else {
            None
        }
    }
}

pub fn add(md: &mut MarkdownIt) {
    md.inline.add_rule::<ImageScanner>();
}
