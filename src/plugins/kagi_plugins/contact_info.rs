use crate::mdparser::constants::{MAIL_PREFIX, PHONE_PREFIX};
use crate::mdparser::inline::{InlineRule, InlineState};
use crate::{MarkdownIt, Node, NodeValue, Renderer};

#[derive(Debug)]
pub enum ContactInfoType {
    Email,
    Phone,
}

#[derive(Debug)]
pub struct ContactInfo {
    pub content: String,
    pub prefix: String,
    pub info_type: ContactInfoType,
}

impl NodeValue for ContactInfo {
    fn render(&self, node: &Node, fmt: &mut dyn Renderer) {
        let mut attrs = node.attrs.clone();

        // NOTE(Rehan): clear out non digit chars (except '+' for area code) from phone number for link
        let cleaned = match self.info_type {
            ContactInfoType::Email => &self.content,
            ContactInfoType::Phone => &self
                .content
                .chars()
                .filter(|c| c.is_ascii_digit() || *c == '+')
                .collect(),
        };

        attrs.push(("href", format!("{}{}", self.prefix, cleaned)));
        fmt.open("a", &attrs);
        fmt.text(&self.content);
        fmt.close("a");
    }
}

struct ContactInfoScanner;

impl InlineRule for ContactInfoScanner {
    const MARKER: char = '<';

    fn run(state: &mut InlineState) -> Option<(Node, usize)> {
        let input = &state.src[state.pos..state.pos_max];

        let end_marker: &str = ">";

        let (prefix, info_type) = match input {
            s if s.starts_with(&format!("{}{}", Self::MARKER, MAIL_PREFIX)) => {
                (MAIL_PREFIX, ContactInfoType::Email)
            }
            s if s.starts_with(&format!("{}{}", Self::MARKER, PHONE_PREFIX)) => {
                (PHONE_PREFIX, ContactInfoType::Phone)
            }
            _ => return None,
        };

        let end = input.find(end_marker)?;

        let matched = &input[..end + 1];

        let content = matched
            .strip_prefix(&format!("{}{}", Self::MARKER, prefix))?
            .strip_suffix(end_marker)?
            .to_string();

        Some((
            Node::new(ContactInfo {
                content,
                prefix: prefix.to_string(),
                info_type,
            }),
            matched.len(),
        ))
    }
}

pub fn add(md: &mut MarkdownIt) {
    md.inline.add_rule::<ContactInfoScanner>();
}
