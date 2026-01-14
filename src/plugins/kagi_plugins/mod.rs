pub mod citation;
pub mod contact_info;
pub mod image;
pub mod inkjet;
pub mod link;
pub mod math;
pub mod math_display;
pub mod math_inline;
pub mod nl2br;
use crate::plugin_config::CitationExtensionPlugin;
use crate::plugins::cmark::{block, inline};
use crate::{ImageExtensionPlugin, InkjetPlugin, LinkExtensionPlugin, MarkdownIt};

// TODO (matt): Move this constant up!!
const URL_SUBSTRING_TO_BE_PROXIED: [&str; 1] = ["https://storage.googleapis.com/kagi"];

/// ```
/// use quickmark::plugins::kagi_plugins::is_url_to_be_proxied;
/// assert_eq!(is_url_to_be_proxied("https://storage.googleapis.com/kagi_stuff/tool_u_123123213.jpg"), true);
/// assert_eq!(is_url_to_be_proxied("https://storage.googleapis.com/kagi_stuff/steve_jobs.png"), true);
/// assert_eq!(is_url_to_be_proxied("https://www.kagi.com"), false);
/// ```
pub fn is_url_to_be_proxied(url: &str) -> bool {
    URL_SUBSTRING_TO_BE_PROXIED
        .iter()
        .any(|&substring| url.contains(substring))
}

// NOTE(Rehan): If updating this, update list of plugin names below
pub fn add(md: &mut MarkdownIt) {
    nl2br::add(md);
    inline::newline::add(md);
    inline::escape::add(md);
    inline::backticks::add(md);
    inline::emphasis::add(md);

    image::add(md, ImageExtensionPlugin::default());
    link::add(md, LinkExtensionPlugin::default());
    citation::add(md, CitationExtensionPlugin::default());
    contact_info::add(md);
    inkjet::add(md, InkjetPlugin::default());

    inline::entity::add(md);
    crate::plugins::html::html_inline::add(md);
    crate::plugins::html::html_block::add(md);
    crate::plugins::extra::tables::add(md);
    math_display::add(
        md,
        crate::plugin_config::DisplayMathExtensionPlugin::default(),
    );
    math_inline::add(
        md,
        crate::plugin_config::InlineMathExtensionPlugin::default(),
    );

    block::code::add(md);
    block::fence::add(md);
    block::blockquote::add(md);
    block::hr::add(md);
    block::list::add(md);
    block::reference::add(md);
    block::heading::add(md);
    block::lheading::add(md);
    block::paragraph::add(md);
}

pub const KAGI_PLUGIN_NAMES: [&str; 23] = [
    "nl2br",
    "newline",
    "escape",
    "backticks",
    "emphasis",
    "kagi_image",
    "kagi_link",
    "kagi_contact_info",
    "inkjet",
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
    "citation",
    "table",
    "inline_math",
    "display_math",
];
