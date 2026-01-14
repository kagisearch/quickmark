//! Frequently used markdown extensions and stuff from GFM.
//!
//!  - strikethrough (~~xxx~~~)
//!  - tables
//!  - linkify (convert http://example.com to a link)
//!  - beautify links (cut "http://" from links and shorten paths)
//!  - smartquotes and typographer
//!
//! ```rust
//! let md = &mut quickmark::MarkdownIt::new();
//! quickmark::plugins::cmark::add(md);
//! quickmark::plugins::extra::add(md);
//!
//! let html = md.parse("hello ~~world~~").render();
//! assert_eq!(html.trim(), r#"<p>hello <s>world</s></p>"#);
//!
//! let html = md.parse(r#"Markdown done "The Right Way(TM)""#).render();
//! assert_eq!(html.trim(), r#"<p>Markdown done “The Right Way™”</p>"#);
//! ```
pub mod beautify_links;
pub mod front_matter;
pub mod gh_flavored_md;
pub mod github_slugger;
pub mod heading_anchors;
#[cfg(feature = "linkify")]
pub mod linkify;
pub mod smartquotes;
pub mod strikethrough;
pub mod tables;
pub mod tasklist;
pub mod typographer;

use crate::MarkdownIt;

pub fn add(md: &mut MarkdownIt) {
    strikethrough::add(md);
    beautify_links::add(md);
    #[cfg(feature = "linkify")]
    linkify::add(md);
    tables::add(md);
    typographer::add(md);
    smartquotes::add(md);
}
