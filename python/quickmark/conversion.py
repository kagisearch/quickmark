from quickmark import (
    MDParser,
    CitationQM,
    Plugin,
    LinkExtensionPlugin,
    ImageExtensionPlugin,
    InlineMathExtensionPlugin,
    DisplayMathExtensionPlugin,
    CitationExtensionPlugin,
)


def md_to_html(
    text: str,
    citations: list[CitationQM] | None = None,
    open_links_in_new_tab: bool = True,
    embed_third_party_content: bool = False,
    remove_links_to_be_proxied: bool = False,
    rust_extensions: list[Plugin] | None = None,
) -> str:
    if rust_extensions is not None:
        rust_extensions = list(rust_extensions)
        rust_extensions.extend(
            [
                Plugin(name="nl2br"),
                Plugin(name="backticks"),  # inline codeblocks
                Plugin(name="escape"),  # allow char escapes
                Plugin(name="emphasis"),
                LinkExtensionPlugin(
                    embed_third_party_content=embed_third_party_content,
                    remove_links_to_be_proxied=remove_links_to_be_proxied,
                    open_links_in_new_tab=open_links_in_new_tab,
                ),
                ImageExtensionPlugin(
                    remove_links_to_be_proxied=remove_links_to_be_proxied,
                ),
                Plugin(name="kagi_contact_info"),
                Plugin(name="entity"),  # html entities
                Plugin(name="blockquote"),
                Plugin(name="hr"),  # markdown line ('---')
                Plugin(name="list"),
                Plugin(name="heading"),
                Plugin(name="paragraph"),
                Plugin(name="html_inline"),
                Plugin(name="html_block"),
                Plugin(name="table"),
                InlineMathExtensionPlugin(cache=True),
                DisplayMathExtensionPlugin(cache=True),
            ]
        )
    else:
        rust_extensions = []
    if citations:
        rust_extensions.append(
            CitationExtensionPlugin(
                citations=[
                    citation.to_quickmark_citation() for citation in citations
                ],
                open_links_in_new_tab=open_links_in_new_tab,
            )
        )
    quickmark_parser = MDParser("zero")
    quickmark_parser.enable_many(rust_extensions)  # type: ignore[reportArgumentType]
    text = quickmark_parser.render(text)
    # Sometimes whitespace at end of line
    # Not same behavior as stdlib markdown
    text = text.strip()
    return text
