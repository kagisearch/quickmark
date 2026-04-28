//! Links
//!
//! `![link](<to> "stuff")`
//!
//! <https://spec.commonmark.org/0.30/#links>
use crate::mdparser::inline::{InlineRule, InlineState};
use crate::{LinkExtensionPlugin, MarkdownIt, Node, NodeValue, Renderer};
use html_escape::decode_html_entities;
use mime_guess;
use once_cell::sync::Lazy;
use regex::Regex;
use url::Url;

use super::is_url_to_be_proxied;

/// Parse Youtube ID from url
///
/// # Examples
///
/// ```
/// use quickmark::plugins::kagi_plugins::link::parse_youtube_id;
/// assert_eq!(parse_youtube_id("https://www.youtube.com/shorts/test_id"), Some("test_id".to_string()));
/// assert_eq!(parse_youtube_id("https://www.youtube.com/watch?v=test_id"), Some("test_id".to_string()));
/// assert_eq!(parse_youtube_id("https://www.youtu.be/test_id"), Some("test_id".to_string()));
/// assert_eq!(parse_youtube_id("https://www.invalid.com"), None);
/// ```
pub static LINK_MD_PATTERN: Lazy<Regex> = Lazy::new(|| {
    // NOTE(Boon): `^` anchor is required. Without it, an unmatched `[...]` followed
    // by a real `](...)` later in the input would cause the scanner to return the
    // byte length of the later match and the caller would advance `state.pos` into
    // the middle of a multi-byte character sitting between the two brackets,
    // panicking with "byte index N is not a char boundary".
    Regex::new(
        r"(?x)
        ^\[
        (?P<link_text>.*?)
        \]
        (?P<open_parenthesis>\()
        (?P<url>[^)]*)
        (?P<close_parenthesis>\))?
        (\n?)
    ",
    )
    .unwrap()
});

pub fn parse_youtube_id(url: &str) -> Option<String> {
    let parsed_url = Url::parse(url).ok()?;

    // Try to get video ID from query parameter 'v'
    if let Some(query_pairs) = parsed_url.query_pairs().find(|(key, _)| key == "v") {
        return Some(query_pairs.1.to_string());
    }

    // If no 'v' parameter found, get the last segment of the path
    let path_final_segment = parsed_url
        .path_segments()
        .and_then(|segments| segments.last())?
        .to_string();

    (!path_final_segment.is_empty()).then_some(path_final_segment)
}

fn parse_url_options(url: &str) -> Option<(bool, bool)> {
    let parse_result = Url::parse(&url).ok()?;
    let netloc = parse_result.host_str()?;
    let extension = parse_result.path();
    let url_type = mime_guess::from_path(extension)
        .first_or_octet_stream()
        .to_string();
    let audio = url_type.starts_with("audio");
    let is_youtube = netloc.contains("youtube.") || netloc.contains("youtu.be");

    Some((audio, is_youtube))
}

#[derive(Debug)]
pub struct Link {
    pub url: Option<String>,
    pub title: String,
    pub close_parenthesis: Option<String>,
    pub config: LinkExtensionPlugin,
}

impl NodeValue for Link {
    fn render(&self, node: &Node, fmt: &mut dyn Renderer) {
        let config = self.config;
        if self.url.is_none() || self.close_parenthesis.is_none() {
            fmt.text(&self.title);
            return;
        }
        let mut attrs = node.attrs.clone();

        let url = self.url.as_ref().unwrap();
        attrs.push(("href", url.clone()));

        let proper_url = if !(url.starts_with("http://") || url.starts_with("https://")) {
            &format!("https://{}", url)
        } else {
            url
        };

        let (audio, is_youtube) = parse_url_options(proper_url).unwrap_or((false, false));

        if is_youtube && config.embed_third_party_content {
            if let Some(video_id) = parse_youtube_id(url) {
                let iframe_attrs = vec![
                    // NOTE(Rehan): taken from share menu in youtube, might want to adjust height and width values in future.
                    ("width", "560".to_string()),
                    ("height", "315".to_string()),
                    ("src", format!("https://www.youtube.com/embed/{}", video_id)),
                    ("frameborder", "0".to_string()),
                    ("allowfullscreen", "true".to_string()),
                ];

                fmt.open("iframe", &iframe_attrs);
                fmt.close("iframe");
                return;
            }
        }
        if is_url_to_be_proxied(url) && audio {
            fmt.open("figure", &[]);
            fmt.open("figcaption", &[]);
            fmt.text(&node.collect_text());
            fmt.close("figcaption");
            let audio_attrs = vec![
                ("controls", "".to_string()), ("src", url.clone())
            ];
            fmt.open("audio", &audio_attrs);
            fmt.close("audio");

            fmt.close("figure");
            return;
        }

        if config.open_links_in_new_tab {
            attrs.push(("target", "_blank".to_string()))
        }
        fmt.open("a", &attrs);
        fmt.contents(&node.children);
        fmt.text(&self.title);
        fmt.close("a");
    }
}

struct LinkScanner;

impl InlineRule for LinkScanner {
    const MARKER: char = '[';

    fn run(state: &mut InlineState) -> Option<(Node, usize)> {
        let input = &state.src[state.pos..state.pos_max];
        if !input.starts_with("[") {
            return None;
        }
        let config = state.md.ext.get::<LinkExtensionPlugin>().unwrap();
        if let Some(caps) = LINK_MD_PATTERN.captures(input) {
            let complete_match = &caps[0];
            let link_text = caps
                .name("link_text")
                .map(|m| decode_html_entities(m.as_str()).to_string())?;
            let url = caps
                .name("url")
                .map(|m| decode_html_entities(m.as_str()).to_string());
            let title = if link_text.is_empty() {
                url.clone().unwrap_or_default()
            } else {
                link_text
            };
            let close_parenthesis: Option<String> = caps
                .name("close_parenthesis")
                .map(|m| decode_html_entities(m.as_str()).to_string());
            Some((
                Node::new(Link {
                    url: url,
                    title,
                    close_parenthesis: close_parenthesis,
                    config: *config,
                }),
                // NOTE(Rehan): trim end to not replace trailing newline
                complete_match.trim_end().len(),
            ))
        } else {
            None
        }
    }
}

pub fn add(md: &mut MarkdownIt, config: LinkExtensionPlugin) {
    md.ext.insert(config);
    md.inline.add_rule::<LinkScanner>();
}


#[cfg(test)]
mod tests {
    use super::LINK_MD_PATTERN;

    #[test]
    fn link_pattern_is_anchored_at_start() {
        // LINK_MD_PATTERN must not match a `](...)` that sits later in the input
        // than the opening `[`, because the scanner uses the match's byte length
        // to advance `state.pos` and assumes the match starts at position 0.
        // Without the `^` anchor, this advance can land mid-character when
        // multi-byte chars sit between an unmatched `[...]` and a real `](...)`,
        // causing "byte index N is not a char boundary" panics (see mdrs_error.json).
        assert!(LINK_MD_PATTERN.captures("[unmatched bracket\nfollowed by [x](y)").is_none());
        assert!(LINK_MD_PATTERN.captures("prefix[x](y)").is_none());
        assert!(LINK_MD_PATTERN.captures("[x](y)").is_some());
    }
}

