// useful asserts that's off by default
#![warn(clippy::manual_assert)]
#![warn(clippy::semicolon_if_nothing_returned)]
//
// these are often intentionally not collapsed for readability
#![allow(clippy::collapsible_else_if)]
#![allow(clippy::collapsible_if)]
#![allow(clippy::collapsible_match)]
//
// these are intentional in bevy systems: nobody is directly calling those,
// so extra arguments don't decrease readability
#![allow(clippy::too_many_arguments)]
#![allow(clippy::type_complexity)]
//
// just a style choice that clippy has no business complaining about
#![allow(clippy::uninlined_format_args)]

pub mod common;
pub mod generics;
pub mod mdparser;
pub mod plugins;

pub use crate::mdparser::main::MarkdownIt;
use crate::plugin_config::{
    CitationExtensionPlugin, DisplayMathExtensionPlugin, InlineMathExtensionPlugin,
};
use crate::plugins::cmark::COMMONMARK_PLUGIN_NAMES;
use crate::plugins::extra::gh_flavored_md::GITHUB_PLUGIN_NAMES;
use crate::plugins::kagi_plugins::citation::CitationQM;
use crate::plugins::kagi_plugins::inkjet::warmup;
use crate::plugins::kagi_plugins::KAGI_PLUGIN_NAMES;
use crate::plugins::kagi_plugins::*;
pub use mdparser::node::{Node, NodeValue};
pub use mdparser::preprocess::preprocess;
pub use mdparser::renderer::Renderer;
use plugin_config::ImageExtensionPlugin;
use plugin_config::InkjetPlugin;
mod plugin_config;
use plugin_config::LinkExtensionPlugin;
use plugin_config::Plugin;

//
//
// Maturin build
//
//
use pyo3::{exceptions::PyRuntimeError, prelude::*};
mod nodes;

use once_cell::sync::Lazy;
use std::{panic, panic::AssertUnwindSafe, panic::PanicHookInfo, sync::Mutex};

// NOTE(Rehan): storage for the most recent panic message
// need to be mutex to be global variable that can be written to on runtime
// even though multiple threads not expected
static LAST_PANIC: Lazy<Mutex<Option<String>>> = Lazy::new(|| Mutex::new(None));

/// throw in our custom panic hook to silence MDRS panics and store the message instead
pub fn init_panic_hook() {
    std::panic::set_hook(Box::new(|info: &PanicHookInfo| {
        // NOTE(Rehan): payload often &str or String, but can be other stuff
        let mut msg = match info.payload().downcast_ref::<&str>() {
            Some(s) => (*s).to_string(),
            None => match info.payload().downcast_ref::<String>() {
                Some(s) => s.clone(),
                None => "Payload not str or string".to_string(),
            },
        };

        // NOTE(Rehan): location part of panic - part that points out line number of file and whatnot
        if let Some(location) = info.location() {
            msg.push_str(&format!(" at {}:{}", location.file(), location.line()));
        }

        *(LAST_PANIC.lock().unwrap()) = Some(msg);
    }));
}

#[derive(FromPyObject)]
enum AnyPlugin<'py> {
    #[pyo3(transparent)]
    Link(PyRef<'py, LinkExtensionPlugin>),

    #[pyo3(transparent)]
    Image(PyRef<'py, ImageExtensionPlugin>),

    #[pyo3(transparent)]
    Citation(PyRef<'py, CitationExtensionPlugin>),

    #[pyo3(transparent)]
    InlineMath(PyRef<'py, InlineMathExtensionPlugin>),

    #[pyo3(transparent)]
    DisplayMath(PyRef<'py, DisplayMathExtensionPlugin>),

    #[pyo3(transparent)]
    Inkjet(PyRef<'py, InkjetPlugin>),

    #[pyo3(transparent)]
    Base(PyRef<'py, Plugin>),
}

/// Main parser class
#[pyclass]
#[derive(Debug)]
pub struct MDParser {
    parser: MarkdownIt,
    enabled_plugin_names: Vec<String>,
}

impl MDParser {
    pub fn _enable_str(&mut self, name: &str) -> Result<(), PyErr> {
        match name {
            "nl2br" => {
                crate::plugins::kagi_plugins::nl2br::add(&mut self.parser);
            }
            "citation" => {
                crate::plugins::kagi_plugins::citation::add(
                    &mut self.parser,
                    CitationExtensionPlugin::default(),
                );
            }
            "blockquote" => {
                crate::plugins::cmark::block::blockquote::add(&mut self.parser);
            }
            "code" => {
                crate::plugins::cmark::block::code::add(&mut self.parser);
            }
            "inkjet" => {
                crate::plugins::kagi_plugins::inkjet::add(
                    &mut self.parser,
                    InkjetPlugin::default(),
                );
            }
            "fence" => {
                crate::plugins::cmark::block::fence::add(&mut self.parser);
            }
            "heading" => {
                crate::plugins::cmark::block::heading::add(&mut self.parser);
            }
            "hr" => {
                crate::plugins::cmark::block::hr::add(&mut self.parser);
            }
            "lheading" => {
                crate::plugins::cmark::block::lheading::add(&mut self.parser);
            }
            "list" => {
                crate::plugins::cmark::block::list::add(&mut self.parser);
            }
            "paragraph" => {
                crate::plugins::cmark::block::paragraph::add(&mut self.parser);
            }
            "reference" => {
                crate::plugins::cmark::block::reference::add(&mut self.parser);
            }
            "autolink" => {
                crate::plugins::cmark::inline::autolink::add(&mut self.parser);
            }
            "kagi_link" => {
                crate::plugins::kagi_plugins::link::add(
                    &mut self.parser,
                    LinkExtensionPlugin::default(),
                );
            }
            "kagi_image" => {
                crate::plugins::kagi_plugins::image::add(
                    &mut self.parser,
                    ImageExtensionPlugin::default(),
                );
            }
            "kagi_contact_info" => {
                crate::plugins::kagi_plugins::contact_info::add(&mut self.parser);
            }
            "backticks" => {
                crate::plugins::cmark::inline::backticks::add(&mut self.parser);
            }
            "emphasis" => {
                crate::plugins::cmark::inline::emphasis::add(&mut self.parser);
            }
            "entity" => {
                crate::plugins::cmark::inline::entity::add(&mut self.parser);
            }
            "escape" => {
                crate::plugins::cmark::inline::escape::add(&mut self.parser);
            }
            "image" => {
                crate::plugins::cmark::inline::image::add(&mut self.parser);
            }
            "link" => {
                crate::plugins::cmark::inline::link::add(&mut self.parser);
            }
            "newline" => {
                crate::plugins::cmark::inline::newline::add(&mut self.parser);
            }
            "html_block" => {
                crate::plugins::html::html_block::add(&mut self.parser);
            }
            "html_inline" => {
                crate::plugins::html::html_inline::add(&mut self.parser);
            }
            "linkify" => {
                crate::plugins::extra::linkify::add(&mut self.parser);
            }
            "replacements" => {
                crate::plugins::extra::typographer::add(&mut self.parser);
            }
            "smartquotes" => {
                crate::plugins::extra::smartquotes::add(&mut self.parser);
            }
            "sourcepos" => {
                crate::plugins::sourcepos::add(&mut self.parser);
            }
            "strikethrough" => {
                crate::plugins::extra::strikethrough::add(&mut self.parser);
            }
            "table" => {
                crate::plugins::extra::tables::add(&mut self.parser);
            }
            "front_matter" => {
                crate::plugins::extra::front_matter::add(&mut self.parser);
            }
            "tasklist" => {
                crate::plugins::extra::tasklist::add(&mut self.parser);
            }
            "footnote" => {
                crate::plugins::footnote::add(&mut self.parser);
            }
            "heading_anchors" => {
                crate::plugins::extra::heading_anchors::add(&mut self.parser);
            }
            "autolink_ext" => {
                crate::plugins::autolinks::add(&mut self.parser);
            }
            "inline_math" => {
                crate::plugins::kagi_plugins::math_inline::add(
                    &mut self.parser,
                    InlineMathExtensionPlugin::default(),
                );
            }
            "display_math" => {
                crate::plugins::kagi_plugins::math_display::add(
                    &mut self.parser,
                    DisplayMathExtensionPlugin::default(),
                );
            }
            _ => {
                return {
                    Err(pyo3::exceptions::PyValueError::new_err(format!(
                        "Unknown plugin: {}",
                        name
                    )))
                }
            }
        }
        Ok(())
    }

    fn _enable(&mut self, py: Python, plugin: Py<Plugin>) -> Result<(), PyErr> {
        match plugin.extract::<AnyPlugin>(py)? {
            AnyPlugin::Link(p) => link::add(&mut self.parser, *p),
            AnyPlugin::Image(p) => image::add(&mut self.parser, *p),
            AnyPlugin::Citation(p) => citation::add(&mut self.parser, p.clone()),
            AnyPlugin::InlineMath(p) => math_inline::add(&mut self.parser, *p),
            AnyPlugin::DisplayMath(p) => math_display::add(&mut self.parser, *p),
            AnyPlugin::Inkjet(p) => inkjet::add(&mut self.parser, *p),
            AnyPlugin::Base(p) => self._enable_str(&p.name)?,
        }
        self.enabled_plugin_names
            .push(plugin.borrow(py).name.clone());

        Ok(())
    }
}

#[pymethods]
impl MDParser {
    #[new]
    #[pyo3(signature = (config="kagi"))]
    pub fn new(config: &str) -> PyResult<Self> {
        match config {
            "kagi" => {
                // NOTE(Rehan): cmark plugins, but replacing their versions with ours where applicable
                // probably should be a better way to do this so we don't have to keep this and `mod.rs` for `kagi_plugins` in sync
                let mut parser = MarkdownIt::new();
                crate::plugins::kagi_plugins::add(&mut parser);
                Ok(Self {
                    parser,
                    enabled_plugin_names: KAGI_PLUGIN_NAMES.iter().map(|s| s.to_string()).collect(),
                })
            }
            "commonmark" => {
                let mut parser = MarkdownIt::new();
                crate::plugins::cmark::add(&mut parser);
                crate::plugins::html::add(&mut parser);
                Ok(Self {
                    parser,
                    enabled_plugin_names: COMMONMARK_PLUGIN_NAMES
                        .iter()
                        .map(|s| s.to_string())
                        .collect(),
                })
            }
            "gfm" => {
                let mut parser = MarkdownIt::new();
                crate::plugins::extra::gh_flavored_md::add(&mut parser);
                // TODO(Rehan): setting names as empty, but not true, plugins are enabled
                Ok(Self {
                    parser,
                    enabled_plugin_names: GITHUB_PLUGIN_NAMES
                        .iter()
                        .map(|s| s.to_string())
                        .collect(),
                })
            }
            "zero" => Ok(Self {
                parser: MarkdownIt::new(),
                enabled_plugin_names: Vec::new(),
            }),
            _ => Err(pyo3::exceptions::PyValueError::new_err(format!(
                "Unknown config: {}",
                config
            ))),
        }
    }

    /// Return a debug representation of the rust struct
    fn _debug(&self) -> String {
        format!("{:#?}", self)
    }

    // keep this private for now, whilst we work out how to expose it properly
    fn _unset_lang_prefix(&mut self) {
        crate::plugins::cmark::block::fence::set_lang_prefix(&mut self.parser, "");
    }

    #[staticmethod]
    fn list_plugins() -> Vec<String> {
        vec![
            "blockquote",
            "code",
            "fence",
            "heading",
            "hr",
            "lheading",
            "list",
            "paragraph",
            "reference",
            "autolink",
            "backticks",
            "emphasis",
            "entity",
            "escape",
            "image",
            "link",
            "newline",
            "html_block",
            "html_inline",
            "linkify",
            "replacements",
            "smartquotes",
            "sourcepos",
            "strikethrough",
            "table",
            "front_matter",
            "tasklist",
            "footnote",
            "heading_anchors",
            "autolink_ext",
        ]
        .iter()
        .map(|s| s.to_string())
        .collect()
    }

    /// Enable a plugin
    fn enable(slf: Py<Self>, py: Python, plugin: Py<Plugin>) -> PyResult<Py<Self>> {
        slf.borrow_mut(py)._enable(py, plugin)?;
        Ok(slf)
    }

    /// Enable multiple plugins
    fn enable_many(slf: Py<Self>, py: Python, plugins: Vec<Py<Plugin>>) -> PyResult<Py<Self>> {
        for plugin in plugins {
            slf.borrow_mut(py)._enable(py, plugin)?;
        }
        Ok(slf)
    }

    /// Render markdown string into HTML.
    /// If `xhtml` is true, then self-closing tags will include a slash, e.g. `<br />`.
    #[pyo3(signature = (src, *, xhtml=true))]
    pub fn render(&self, src: &str, xhtml: bool) -> PyResult<String> {
        let result = panic::catch_unwind(AssertUnwindSafe(|| {
            let preprocessed = preprocess(src, &self.enabled_plugin_names);
            let ast = self.parser.parse(preprocessed.as_ref());
            match xhtml {
                true => ast.xrender(),
                false => ast.render(),
            }
        }));

        match result {
            Ok(html) => Ok(html),
            Err(_) => {
                // unwrap ok here, can only be error if another thread doesn't let go of mutex
                // but we don't expect that, one panic and we send the error up and stop
                let lock_result = LAST_PANIC.lock();
                let msg = match lock_result {
                    Err(_) => "mutex lock failed".to_owned(),
                    Ok(mut lock) => lock
                        .take()
                        .unwrap_or_else(|| "Rust panic occurred".to_owned()),
                };

                Err(PyRuntimeError::new_err(msg))
            }
        }
    }
    /// Create a syntax tree from the markdown string.
    fn tree(&self, py: Python, src: &str) -> nodes::Node {
        let ast = self.parser.parse(src);

        fn walk_recursive(py: Python, node: &crate::Node, py_node: &mut nodes::Node) {
            for n in node.children.iter() {
                let mut py_node_child = nodes::create_node(py, n);

                stacker::maybe_grow(64 * 1024, 1024 * 1024, || {
                    walk_recursive(py, n, &mut py_node_child);
                });

                py_node.children.push(Py::new(py, py_node_child).unwrap());
            }
        }

        let mut py_node = nodes::create_node(py, &ast);
        walk_recursive(py, &ast, &mut py_node);
        py_node
    }

    /// warmup for quickmark
    fn warmup(&self, _py: Python) {
        let _ = warmup();
    }
}

#[pymodule]
// Note: The name of this function must match the `lib.name` setting in the `Cargo.toml`,
// else Python will not be able to import the module.
fn quickmark(m: &Bound<'_, PyModule>) -> PyResult<()> {
    init_panic_hook();
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add_class::<MDParser>()?;
    m.add_class::<nodes::Node>()?;
    m.add_class::<Plugin>()?;
    m.add_class::<ImageExtensionPlugin>()?;
    m.add_class::<LinkExtensionPlugin>()?;
    m.add_class::<CitationExtensionPlugin>()?;
    m.add_class::<CitationQM>()?;
    m.add_class::<InlineMathExtensionPlugin>()?;
    m.add_class::<DisplayMathExtensionPlugin>()?;
    m.add_class::<InkjetPlugin>()?;
    // let plugins_module = PyModule::new(py, "plugins")?;
    // plugins_module.add_function(wrap_pyfunction!(plugins::add_heading_anchors, plugins_module)?)?;
    // m.add_submodule(plugins_module)?;
    Ok(())
}
