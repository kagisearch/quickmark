//! this file just holds the function to convert from mathml to html
//! keep here for reuse between inline math and siplay math modules, as well as applying caching
use cached::proc_macro::cached;
use html_escape::encode_text;
use once_cell::sync::Lazy;
use pulldown_latex::config::DisplayMode;
use pulldown_latex::RenderConfig;
use pulldown_latex::{mathml::push_mathml, Parser, Storage};
use regex::Regex;
static BOXED_MACRO_REGEX: Lazy<Regex> = Lazy::new(|| Regex::new(r"\\boxed\b").unwrap());

#[cached(size = 128)]
pub fn math_render_cached(math: String, block_display_mode: bool) -> String {
    math_render(math, block_display_mode)
}

pub fn math_render(math: String, block_display_mode: bool) -> String {
    // pulldown_latex doesn't support \boxed; rewrite to \mathbf so it renders
    // as bold. Python's latex2mathml pipeline applies the same rewrite.
    let math = BOXED_MACRO_REGEX
        .replace_all(&math, r"\mathbf")
        .into_owned();
    let storage = Storage::new();
    let parser = Parser::new(&math, &storage);
    let mut config: RenderConfig = Default::default();
    config.display_mode = if block_display_mode {
        DisplayMode::Block
    } else {
        DisplayMode::Inline
    };
    let mut mathml = String::new();

    // NOTE(Rehan): some parsing errors show up in the actual converted text for whatever reason (not raised as an error)
    // so we manually parse the text for the error strings to avoid presenting that to the user
    match push_mathml(&mut mathml, parser, config) {
        Ok(()) => {
            if mathml.contains("parsing error") && mathml.contains("╭─►") {
                encode_text(&math).to_string()
            } else {
                mathml
            }
        }
        Err(_) => encode_text(&math).to_string(),
    }
}
