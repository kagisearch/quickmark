//! A [markdown_it] plugin for parsing footnotes
//!
//! ```
//! let parser = &mut quickmark::MarkdownIt::new();
//! quickmark::plugins::footnote::add(parser);
//! let node = parser.parse("[^note]\n\n[^note]: A footnote\n");
//! ```
//!
//!
//!
// # footnote.rs
// A plugin to process footnotes.
// It is based on the [pandoc definition](http://johnmacfarlane.net/pandoc/README.html#footnotes):
// ```md
// Normal footnote:
// Here is a footnote reference,[^1] and another.[^longnote]
// Here is an inline note.^[my note is here!]
// [^1]: Here is the footnote.
// [^longnote]: Here's one with multiple blocks.
//     Subsequent paragraphs are indented to show that they
// belong to the previous footnote.
// ```
// See the [tests](tests/fixtures) for more examples.
// ## Usage
// To load the full plugin:
// ```rust
// let parser = &mut crate::MarkdownIt::new();
// crate::plugins::cmark::add(parser);
// quickmark::plugins::footnote::add(parser);
// let ast  = parser.parse("Example^[my note]");
// let html = ast.render();
// ```
// Alternatively, you can load the separate components:
// ```rust
// let parser = &mut crate::MarkdownIt::new();
// crate::plugins::cmark::add(parser);
// quickmark::plugins::footnote::definitions::add(md);
// quickmark::plugins::footnote::references::add(md);
// quickmark::plugins::footnote::inline::add(md);
// quickmark::plugins::footnote::collect::add(md);
// quickmark::plugins::footnote::back_refs::add(md);
// ```
// Which have the following roles:
//
// - `definitions`: parse footnote definitions, e.g. `[^1]: foo`
//
// - `references`: parse footnote references, e.g. `[^1]`
//
// - `inline`: parse inline footnotes, e.g. `^[foo]`
//
// - `collect`: collect footnote definitions (removing duplicate/unreferenced ones) and move them to be the last child of the root node.
//
// - `back_refs`: add anchor(s) to footnote definitions, with links back to the reference(s)
//
use std::collections::HashMap;

use crate::{mdparser::extset::RootExt, MarkdownIt};

pub mod back_refs;
pub mod collect;
pub mod definitions;
pub mod inline;
pub mod references;

/// Add the full footnote plugin to the parser
pub fn add(md: &mut MarkdownIt) {
    definitions::add(md);
    references::add(md);
    inline::add(md);
    collect::add(md);
    back_refs::add(md);
}

#[derive(Debug, Default)]
/// The set of parsed footnote definition labels,
/// stored in the root node.
pub struct FootnoteMap {
    def_counter: usize,
    ref_counter: usize,
    label_to_def: HashMap<String, usize>,
    def_to_refs: HashMap<usize, Vec<usize>>,
}
impl RootExt for FootnoteMap {}
impl FootnoteMap {
    /// Create an ID for the definition,
    /// or return None if a definition already exists for the label
    pub fn add_def(&mut self, label: &str) -> Option<usize> {
        if self.label_to_def.contains_key(label) {
            return None;
        }
        self.def_counter += 1;
        self.label_to_def
            .insert(String::from(label), self.def_counter);
        Some(self.def_counter)
    }
    /// Create an ID for the reference and return (def_id, ref_id),
    /// or return None if no definition exists for the label
    pub fn add_ref(&mut self, label: &str) -> Option<(usize, usize)> {
        match self.label_to_def.get(label) {
            Some(def_id) => {
                self.ref_counter += 1;
                // self.def_to_refs.get_mut(&def_id).unwrap().push(self.ref_counter);
                match self.def_to_refs.get_mut(def_id) {
                    Some(refs) => refs.push(self.ref_counter),
                    None => {
                        self.def_to_refs.insert(*def_id, vec![self.ref_counter]);
                    }
                }
                Some((*def_id, self.ref_counter))
            }
            None => None,
        }
    }
    /// Add an inline definition and return (def_id, ref_id)
    pub fn add_inline_def(&mut self) -> (usize, usize) {
        self.def_counter += 1;
        self.ref_counter += 1;
        self.def_to_refs
            .insert(self.def_counter, vec![self.ref_counter]);
        (self.def_counter, self.ref_counter)
    }
    /// return the IDs of all references to the given definition ID
    pub fn referenced_by(&self, def_id: usize) -> Vec<usize> {
        match self.def_to_refs.get(&def_id) {
            Some(ids) => ids.clone(),
            None => Vec::new(),
        }
    }
}
