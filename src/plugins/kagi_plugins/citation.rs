use crate::mdparser::inline::{InlineRule, InlineState};
use crate::plugin_config::CitationExtensionPlugin;
use crate::{MarkdownIt, Node, NodeValue, Renderer};
use pyo3::prelude::*;

const OPEN_CITATION: char = '【';
const CLOSE_CITATION: char = '】';

#[pyclass]
#[derive(Debug, Clone)]
pub struct CitationQM {
    pub index: usize,
    pub title: String,
    pub source: String,
    pub passage: String,
    pub md_offset: usize,
}

#[pymethods]
impl CitationQM {
    #[new]
    fn new(
        index: usize,
        title: String,
        source: String,
        passage: String,
        md_offset: usize,
    ) -> PyClassInitializer<Self> {
        PyClassInitializer::from(CitationQM {
            index,
            title,
            source,
            passage,
            md_offset,
        })
    }
}

// NOTE(Rehan): port of `.to_html` method of python citation class
pub fn citation_to_html(
    is_url_source: bool,
    source: &str,
    index: usize,
    open_in_new_tab: bool,
) -> String {
    if is_url_source {
        let target_attr = if open_in_new_tab {
            r#" target="_blank""#
        } else {
            ""
        };

        format!(
            r#"<a href="{url}"{target}>{index}</a>"#,
            url = source,
            target = target_attr,
            index = index
        )
    } else {
        format!(r#"<a>{}</a>"#, index)
    }
}

#[derive(Debug)]
pub struct CitationNode {
    pub citation: CitationQM,
    pub open_link_in_new_tab: bool,
}

impl NodeValue for CitationNode {
    fn render(&self, node: &Node, fmt: &mut dyn Renderer) {
        let attrs = node.attrs.clone();
        let citation_html = citation_to_html(
            self.citation.source.starts_with("http"),
            &self.citation.source,
            self.citation.index,
            self.open_link_in_new_tab,
        );
        fmt.open("sup", &attrs);
        fmt.text_raw(&citation_html);
        fmt.close("sup");
    }
}

struct CitationInlineScanner;

impl InlineRule for CitationInlineScanner {
    const MARKER: char = OPEN_CITATION;

    fn run(state: &mut InlineState) -> Option<(Node, usize)> {
        let input = &state.src[state.pos..state.pos_max];
        if !input.starts_with(OPEN_CITATION) || !input.contains(CLOSE_CITATION) {
            return None;
        }
        let config = state.md.ext.get::<CitationExtensionPlugin>().unwrap();

        let citation_match = input.split_inclusive(CLOSE_CITATION).next()?;

        let citation_index: usize = citation_match
            .strip_prefix(OPEN_CITATION)?
            .strip_suffix(CLOSE_CITATION)?
            .parse()
            .ok()?;

        let citation = config
            .citations
            .get(citation_index)?    
            .clone();

        Some((
            Node::new(CitationNode {
                citation,
                open_link_in_new_tab: config.open_links_in_new_tab,
            }),
            citation_match.len(),
        ))
    }
}

pub fn add(md: &mut MarkdownIt, config: CitationExtensionPlugin) {
    md.ext.insert(config);
    md.inline.add_rule::<CitationInlineScanner>();
}
