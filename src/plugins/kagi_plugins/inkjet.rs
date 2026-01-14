//! Syntax highlighting for code blocks
use crate::common::utils::unescape_all;
use inkjet::{
    constants::HIGHLIGHT_CLASS_NAMES, formatter::Formatter, tree_sitter_highlight::HighlightEvent,
    Highlighter, Language, Result,
};
use v_htmlescape;

use crate::mdparser::block::{BlockRule, BlockState};
use crate::mdparser::constants::INKJET_TO_PYGMENTS_CLASS_MAP;
use crate::plugin_config::InkjetPlugin;
use crate::{MarkdownIt, Node, NodeValue, Renderer};
use std::cell::RefCell;

pub const CODE_HIGHLIGHT_SUFFIX: &str = "</code></pre></div>";
// NOTE(Rehan): if we want to reuse the highlighter, it needs to be mutable
// `thread_local!` runs once per thread. `RefCell` moves compile time borrow to runtime.
// We only run one thread and only run this once on the thread, so this shouldn't really matter
thread_local! {
    static HIGHLIGHTER: RefCell<Highlighter> =
        RefCell::new(Highlighter::new());
}
pub struct PygmentsCompatibleFormatter {
    pub pygments_classes: bool,
}

// NOTE(Rehan): based implementation here on default html formatter: https://docs.rs/crate/inkjet/latest/source/src/formatter/html.rs
// main change is just mapping to pygments classes
impl Formatter for PygmentsCompatibleFormatter {
    fn write<W>(&self, source: &str, writer: &mut W, event: HighlightEvent) -> Result<()>
    where
        W: std::fmt::Write,
    {
        match event {
            HighlightEvent::Source { start, end } => {
                let span = source
                    .get(start..end)
                    .expect("Source bounds should be in bounds!");
                write!(writer, "{}", v_htmlescape::escape(span))?;
            }
            HighlightEvent::HighlightStart(idx) => {
                let inkjet_class = HIGHLIGHT_CLASS_NAMES[idx.0];
                let output_class: &&str = if self.pygments_classes {
                    INKJET_TO_PYGMENTS_CLASS_MAP
                        .get(inkjet_class)
                        .unwrap_or(&inkjet_class)
                } else {
                    &inkjet_class
                };
                write!(writer, "<span class=\"{}\">", output_class)?;
            }
            HighlightEvent::HighlightEnd => {
                writer.write_str("</span>")?;
            }
        }
        Ok(())
    }
}

#[derive(Debug)]
pub struct InkjetCodeFence {
    pub info: String,
    pub marker: char,
    pub marker_len: usize,
    pub content: String,
    pub use_pygments: bool,
}

impl NodeValue for InkjetCodeFence {
    fn render(&self, node: &Node, fmt: &mut dyn Renderer) {
        let info = unescape_all(&self.info);
        let mut split = info.split_whitespace();
        let lang_name = split.next().unwrap_or("");
        let mut attrs = node.attrs.clone();

        if !lang_name.is_empty() {
            attrs.push(("class", lang_name.to_string()));
        }

        let formatter = PygmentsCompatibleFormatter {
            pygments_classes: self.use_pygments,
        };

        let lang_enum = Language::from_token(lang_name).unwrap_or(Language::Plaintext);

        let html = HIGHLIGHTER.with_borrow_mut(|h| {
            h.highlight_to_string(lang_enum, &formatter, self.content.clone())
                .unwrap()
        });

        // NOTE(Rehan): this is what our python code highlighting extension has wrapped around the actual highlighted code
        // so we'll wrap here as well for compatibility
        // `class="codehilite"` from SuperFences extension, `class="filename"` from Highlight extension

        let html = format!(
            "<div class=\"codehilite\">\
                    <span class=\"filename\">{:?}</span>\
                    <pre><span></span><code>{html}{CODE_HIGHLIGHT_SUFFIX}",
            lang_enum,
        );

        fmt.cr();
        fmt.text_raw(&html);
        fmt.cr();
    }
}

pub fn add(md: &mut MarkdownIt, config: InkjetPlugin) {
    md.ext.insert(config);
    md.block.add_rule::<InkjetFenceScanner>();
}

// NOTE(Rehan): copied over from fence.rs, pushed in inkjet rendering
#[doc(hidden)]
pub struct InkjetFenceScanner;

impl InkjetFenceScanner {
    fn get_header<'a>(state: &'a mut BlockState) -> Option<(char, usize, &'a str)> {
        if state.line_indent(state.line) >= state.md.max_indent {
            return None;
        }

        let line = state.get_line(state.line);
        let mut chars = line.chars();

        let marker = chars.next()?;
        if marker != '~' && marker != '`' {
            return None;
        }

        // scan marker length
        let mut len = 1;
        while Some(marker) == chars.next() {
            len += 1;
        }

        // NOTE(Rehan): skip if fences are on same line
        if line.matches("```").count() != 1 {
            return None;
        }

        if len < 3 {
            return None;
        }

        let params = &line[len..];

        if marker == '`' && params.contains(marker) {
            return None;
        }

        Some((marker, len, params))
    }
}

impl BlockRule for InkjetFenceScanner {
    fn check(state: &mut BlockState) -> Option<()> {
        Self::get_header(state).map(|_| ())
    }

    fn run(state: &mut BlockState) -> Option<(Node, usize)> {
        let (marker, len, params) = Self::get_header(state)?;
        let params = params.to_owned();

        let mut next_line = state.line;
        let mut have_end_marker = false;

        // search end of block
        'outer: loop {
            next_line += 1;
            if next_line >= state.line_max {
                // unclosed block should be autoclosed by end of document.
                // also block seems to be autoclosed by end of parent
                break;
            }

            let line = state.get_line(next_line);

            if !line.is_empty() && state.line_indent(next_line) < 0 {
                // non-empty line with negative indent should stop the list:
                // - ```
                //  test
                break;
            }

            let mut chars = line.chars().peekable();

            if Some(marker) != chars.next() {
                continue;
            }

            if state.line_indent(next_line) >= state.md.max_indent {
                continue;
            }

            // scan marker length
            let mut len_end = 1;
            while Some(&marker) == chars.peek() {
                chars.next();
                len_end += 1;
            }

            // closing code fence must be at least as long as the opening one
            if len_end < len {
                continue;
            }

            // make sure tail has spaces only
            loop {
                match chars.next() {
                    Some(' ' | '\t') => {}
                    Some(_) => continue 'outer,
                    None => {
                        have_end_marker = true;
                        break 'outer;
                    }
                }
            }
        }

        // If a fence has heading spaces, they should be removed from its inner block
        let indent = state.line_offsets[state.line].indent_nonspace;
        let (content, _) = state.get_lines(state.line + 1, next_line, indent as usize, true);

        let use_pygments = state.md.ext.get::<InkjetPlugin>().unwrap().pygments_classes;

        let node = Node::new(InkjetCodeFence {
            info: params,
            marker,
            marker_len: len,
            content,
            use_pygments,
        });

        Some((
            node,
            next_line - state.line + if have_end_marker { 1 } else { 0 },
        ))
    }
}

/// call all configs to ensure they're all built
pub fn warmup() {
    for lang in Language::ALL_LANGS.iter() {
        let _ = lang.config();
    }
}
