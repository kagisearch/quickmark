//! Code fence
//!
//! ` ```lang ` or `~~~lang`
//!
//! <https://spec.commonmark.org/0.30/#code-fence>
use crate::common::utils::unescape_all;
use crate::mdparser::block::{BlockRule, BlockState};
use crate::mdparser::extset::MarkdownItExt;
use crate::{MarkdownIt, Node, NodeValue, Renderer};

#[derive(Debug)]
pub struct CodeFence {
    pub info: String,
    pub marker: char,
    pub marker_len: usize,
    pub content: String,
    pub lang_prefix: &'static str,
}

impl NodeValue for CodeFence {
    fn render(&self, node: &Node, fmt: &mut dyn Renderer) {
        let info = unescape_all(&self.info);
        let mut split = info.split_whitespace();
        let lang_name = split.next().unwrap_or("");
        let mut attrs = node.attrs.clone();
        let class;

        if !lang_name.is_empty() {
            class = format!("{}{}", self.lang_prefix, lang_name);
            attrs.push(("class", class));
        }

        // NOTE(Rehan): this is what our python code highlighting extension has wrapped around the actual highlighted code
        // so we'll wrap here as well for compatibility
        // `class="codehilite"` from SuperFences extension, `class="filename"` from Highlight extension
        //
        // wrapping here as well as inkjet so we can have fenced codeblocks sit in a proper codeblock section with a header and everything
        // while streaming. This looks nicer and wont be as jarring when the final pass highlights properly
        //
        // we currently wrap the string manually in the inkjet plugin because the html is already converted, so we output raw text.
        // Here it isn't converted, so we use `fmt` to open/close elements around the code content.
        fmt.cr();
        fmt.open("div", &[("class", "codehilite".to_string())]);
        fmt.open("span", &[("class", "filename".to_string())]);
        fmt.text(lang_name);
        fmt.close("span");
        fmt.open("pre", &[]);
        fmt.open("span", &[]);
        fmt.close("span");
        fmt.open("code", &[]);
        fmt.text(&self.content);
        fmt.close("code");
        fmt.close("pre");
        fmt.close("div");
        fmt.cr();
    }
}

#[derive(Debug, Clone, Copy)]
struct FenceSettings(&'static str);
impl MarkdownItExt for FenceSettings {}

impl Default for FenceSettings {
    fn default() -> Self {
        Self("language-")
    }
}

pub fn add(md: &mut MarkdownIt) {
    md.block.add_rule::<FenceScanner>();
}

pub fn set_lang_prefix(md: &mut MarkdownIt, lang_prefix: &'static str) {
    md.ext.insert(FenceSettings(lang_prefix));
}

#[doc(hidden)]
pub struct FenceScanner;

impl FenceScanner {
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

impl BlockRule for FenceScanner {
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

        let lang_prefix = state
            .md
            .ext
            .get::<FenceSettings>()
            .copied()
            .unwrap_or_default()
            .0;
        let node = Node::new(CodeFence {
            info: params,
            marker,
            marker_len: len,
            content,
            lang_prefix,
        });
        Some((
            node,
            next_line - state.line + if have_end_marker { 1 } else { 0 },
        ))
    }
}
