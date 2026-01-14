use crate::{mdparser::extset::MarkdownItExt, plugins::kagi_plugins::citation::CitationQM};
use pyo3::prelude::*;

// NOTE(Rehan): instructions on creating new plugin:
// - add string name in `_enable_str`
// - add to `add` method in `mod.rs`
// - add to `KAGI_PLUGIN_NAMES`
//
// Instructions on adding config for plugin:
// - create new struct that subclasses `Plugin` (using `#[pyclass(extends = Plugin)]`)
// - impl `MarkdownItExt` for the subclass
// - setup `new` method for sublass (look at `LinkExtensionPlugin` below as an example)
// - add handling in `_enable` to send it down to `add` method for plugin
// - add config class to `quickmark` method in `lib.rs`
// - add type hints in `quickmark.pyi` for the python object (`LinkExtensionPlugin` in `quickmark.pyi` as example)
// - now you can use it
//   - in your plugins `add` method, insert config object in `md.ext` set
//   - in run function, use `get` method on `md.ext` to grab config
//   - if you need config in `render`, you can add a config field to the node struct to pass it in

#[pyclass(subclass)]
pub struct Plugin {
    #[pyo3(get)]
    pub name: String,
}

#[pymethods]
impl Plugin {
    #[new]
    fn new(name: String) -> Self {
        Plugin { name }
    }
}

#[pyclass(extends = Plugin)]
#[derive(Debug, Clone, Copy)]
pub struct LinkExtensionPlugin {
    #[pyo3(get)]
    pub embed_third_party_content: bool,
    #[pyo3(get)]
    pub remove_links_to_be_proxied: bool,
    #[pyo3(get)]
    pub open_links_in_new_tab: bool,
}

impl MarkdownItExt for LinkExtensionPlugin {}

impl Default for LinkExtensionPlugin {
    fn default() -> Self {
        Self {
            embed_third_party_content: false,
            remove_links_to_be_proxied: true,
            open_links_in_new_tab: true,
        }
    }
}
#[pymethods]
impl LinkExtensionPlugin {
    #[new]
    fn new(
        embed_third_party_content: bool,
        remove_links_to_be_proxied: bool,
        open_links_in_new_tab: bool,
    ) -> PyClassInitializer<Self> {
        PyClassInitializer::from(Plugin {
            name: "kagi_link".to_string(),
        })
        .add_subclass(LinkExtensionPlugin {
            embed_third_party_content,
            remove_links_to_be_proxied,
            open_links_in_new_tab,
        })
    }
}

#[pyclass(extends = Plugin)]
#[derive(Debug, Clone)]
pub struct CitationExtensionPlugin {
    #[pyo3(get)]
    pub citations: Vec<CitationQM>,
    #[pyo3(get)]
    pub open_links_in_new_tab: bool,
}

impl MarkdownItExt for CitationExtensionPlugin {}

impl Default for CitationExtensionPlugin {
    fn default() -> Self {
        Self {
            citations: vec![],
            open_links_in_new_tab: true,
        }
    }
}
#[pymethods]
impl CitationExtensionPlugin {
    #[new]
    fn new(citations: Vec<CitationQM>, open_links_in_new_tab: bool) -> PyClassInitializer<Self> {
        PyClassInitializer::from(Plugin {
            name: "citation".to_string(),
        })
        .add_subclass(CitationExtensionPlugin {
            citations,
            open_links_in_new_tab,
        })
    }
}

#[pyclass(extends = Plugin)]
#[derive(Debug, Clone, Copy)]
pub struct ImageExtensionPlugin {
    #[pyo3(get)]
    pub remove_links_to_be_proxied: bool,
}

impl MarkdownItExt for ImageExtensionPlugin {}

impl Default for ImageExtensionPlugin {
    fn default() -> Self {
        Self {
            remove_links_to_be_proxied: true,
        }
    }
}
#[pymethods]
impl ImageExtensionPlugin {
    #[new]
    fn new(remove_links_to_be_proxied: bool) -> PyClassInitializer<Self> {
        PyClassInitializer::from(Plugin {
            name: "kagi_image".to_string(),
        })
        .add_subclass(ImageExtensionPlugin {
            remove_links_to_be_proxied,
        })
    }
}

#[pyclass(extends = Plugin)]
#[derive(Debug, Clone, Copy)]
pub struct InlineMathExtensionPlugin {
    #[pyo3(get)]
    pub cache: bool,
}

impl MarkdownItExt for InlineMathExtensionPlugin {}

impl Default for InlineMathExtensionPlugin {
    fn default() -> Self {
        Self { cache: true }
    }
}
#[pymethods]
impl InlineMathExtensionPlugin {
    #[new]
    fn new(cache: bool) -> PyClassInitializer<Self> {
        PyClassInitializer::from(Plugin {
            name: "inline_math".to_string(),
        })
        .add_subclass(InlineMathExtensionPlugin { cache })
    }
}

#[pyclass(extends = Plugin)]
#[derive(Debug, Clone, Copy)]
pub struct DisplayMathExtensionPlugin {
    #[pyo3(get)]
    pub cache: bool,
}

impl MarkdownItExt for DisplayMathExtensionPlugin {}

impl Default for DisplayMathExtensionPlugin {
    fn default() -> Self {
        Self { cache: true }
    }
}
#[pymethods]
impl DisplayMathExtensionPlugin {
    #[new]
    fn new(cache: bool) -> PyClassInitializer<Self> {
        PyClassInitializer::from(Plugin {
            name: "display_math".to_string(),
        })
        .add_subclass(DisplayMathExtensionPlugin { cache })
    }
}

#[pyclass(extends = Plugin)]
#[derive(Debug, Clone, Copy)]
pub struct InkjetPlugin {
    #[pyo3(get)]
    pub pygments_classes: bool,
}

impl MarkdownItExt for InkjetPlugin {}

impl Default for InkjetPlugin {
    fn default() -> Self {
        Self {
            pygments_classes: true,
        }
    }
}
#[pymethods]
impl InkjetPlugin {
    #[new]
    fn new(pygments_classes: bool) -> PyClassInitializer<Self> {
        PyClassInitializer::from(Plugin {
            name: "inkjet".to_string(),
        })
        .add_subclass(InkjetPlugin { pygments_classes })
    }
}
