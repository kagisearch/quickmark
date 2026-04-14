import textwrap

from quickmark.conversion import md_to_html
from quickmark import (
    CitationExtensionPlugin,
    CitationQM,
    ImageExtensionPlugin,
    InkjetPlugin,
    LinkExtensionPlugin,
    Plugin,
)
import quickmark


class TestLinkProcessor:
    async def test_normal_link_unaffected(self):
        md_text = "This is an [example](https://www.example.com)."
        html_text = md_to_html(md_text)
        assert '<a href="https://www.example.com"' in html_text

    async def test_codeblock(self):
        md_text = "`[example](https://www.example.com).`"
        html_text = md_to_html(md_text)
        assert '<a href="https://www.example.com"' not in html_text

    async def test_image(self):
        md_text = "This is an ![image](https://www.example.com/image.png)."
        html_text = md_to_html(md_text)
        assert "<img" in html_text

    async def test_image_empty_alt_text(self):
        md_text = "This is an ![](https://www.example.com/image.png)."
        html_text = md_to_html(md_text)
        assert "<img" in html_text
        assert "https://www.example.com/image.png" in html_text

    async def test_link_empty_text_falls_back_to_url(self):
        md_text = "Check [](https://www.example.com/page) out."
        html_text = md_to_html(md_text)
        assert '<a href="https://www.example.com/page"' in html_text
        assert "https://www.example.com/page</a>" in html_text

    async def test_open_in_new_tab(self):
        md_text = "This is an [link](https://www.example.com/link)."
        html_text = md_to_html(md_text, open_links_in_new_tab=True)
        assert 'target="_blank"' in html_text

    async def test_square_brackets_link_text(self):
        md_text = "This is an [link and these are [square brackets]](https://www.example.com/link)."
        html_text = md_to_html(md_text)
        assert '<a href="https://www.example.com/link"' in html_text
        assert "link and these are [square brackets]" in html_text


class TestContactInfo:
    """
    Tests for phone numbers and emails
    """

    def test_phone_email_basic(self):
        output = md_to_html(
            "My phone number is 416-555-0147 and my email is guy@example.com"
        )
        expected_output = '<p>My phone number is <a href="tel:4165550147">416-555-0147</a> and my email is <a href="mailto:guy@example.com">guy@example.com</a></p>'
        assert output == expected_output

    def test_phone_email_complex(self):
        output = md_to_html(
            "+1 (999) 999-9999 is a phone number with a country code, and user+tag.with-symbols_123@sub-domain.example-site.co.uk is a pretty crazy email."
        )
        expected_output = '<p><a href="tel:+19999999999">+1 (999) 999-9999</a> is a phone number with a country code, and <a href="mailto:user+tag.with-symbols_123@sub-domain.example-site.co.uk">user+tag.with-symbols_123@sub-domain.example-site.co.uk</a> is a pretty crazy email.</p>'
        assert output == expected_output

    # NOTE(Rehan): Above are new tests, below ported over from `test_postprocess.py`
    # tests not exactly the same, minor formatting changes (quickmark will always surround number with quotation marks)

    def test_plain_phone_number(self):
        text = "Contact me at 123-456-7890."
        output = md_to_html(text)
        assert '<a href="tel:1234567890">123-456-7890</a>' in output

    def test_phone_number_with_parentheses(self):
        text = "For general ticket sales and inquiries: (800)-515-2171."
        output = md_to_html(text)
        assert ': <a href="tel:8005152171">(800)-515-2171</a>' in output

    def test_phone_number_with_double_parentheses(self):
        text = "Hotline For Canada: ((877)-529-7746)."
        output = md_to_html(text)
        assert ': (<a href="tel:8775297746">(877)-529-7746</a>)' in output

    def test_phone_number_with_dots(self):
        text = "Phone number can also be formatted with dots: 123.456.7890."
        output = md_to_html(text)
        assert ': <a href="tel:1234567890">123.456.7890</a>' in output

    def test_phone_number_with_spaces(self):
        text = "Contact me at +12 123-456-7890 or email me at john.doe@amazon.co.jp"
        output = md_to_html(text)
        assert (
            'Contact me at <a href="tel:+121234567890">+12 123-456-7890</a>'
            in output
        )

    def test_phone_number_with_email(self):
        text = "You can reach the support team at 1-800-123-4567 or email them at support@kaggle.com."
        output = md_to_html(text)
        assert '<a href="tel:18001234567">1-800-123-4567</a>' in output
        assert (
            '<a href="mailto:support@kaggle.com">support@kaggle.com</a>'
            in output
        )

    def test_phone_number_preceded_by_open_parenthesis(self):
        text = "(123-456-7890"
        output = md_to_html(text)
        assert '<a href="tel:1234567890">123-456-7890</a>' in output

    def test_ignore_phone_number_preceded_by_non_whitespace_char(self):
        text = "This is a phone number:123-456-7890."
        output = md_to_html(text)
        assert "tel:" not in output

    def test_ignore_phone_number_in_url(self):
        url = "https://www.example.com/p/Multi-Purpose-Synthetic-Oil-Bottle-PTFE-ISO-100-150-51008/304673224"
        text = f"This does not contain phone number: {url}."
        output = md_to_html(text)
        assert "tel:" not in output

    # NOTE(Rehan): math extension not up, so not applicable as of yet
    # def test_ignore_latex(self):
    #     text = "This may look like a phone number $123.4567890$ but it is not."
    #     output = md_to_html(text)
    #     assert '<span><math xmlns="http://www.w3.org/1998/Math/MathML" display="inline">' in output
    #     assert '<a href="tel:' not in output

    def test_ignore_url(self):
        text = "This does not contain a phone number: [https://evolution-outreach.biomedcentral.com/articles/10.1007/s12052-010-0226-0](https://evolution-outreach.biomedcentral.com/articles/10.1007/s12052-010-0226-0)."
        output = md_to_html(text)
        assert '<a href="https://' in output
        assert '<a href="tel:' not in output

    def test_email_in_url(self):
        text = "This is a link with an email-like string in url: https://www.postgresql.org/message-id/40FB2AE5907F9743A593A85015F157BF060BB3A1@ARG-EXVS03.corp.argushealth.com"
        output = md_to_html(text)
        assert '<a href="mailto' not in output


def test_nl2b():
    md_text = "hi\nhi\nhi"
    extensions = [Plugin("nl2br"), Plugin("paragraph")]
    html_text = md_to_html(md_text, rust_extensions=extensions)
    assert html_text.count("<br />") == 2


class TestCitationProcessor:
    def test_citation(self):
        md_text = "Steve Jobs was a human being 【1】"
        html_text = md_to_html(
            md_text,
            rust_extensions=[
                CitationExtensionPlugin(
                    citations=[
                        CitationQM(
                            index=1,
                            title="title",
                            source="http://www.example.com",
                            passage="passage",
                            md_offset=29,
                        ),
                    ],
                    open_links_in_new_tab=False,
                ),
                quickmark.Plugin(name="paragraph"),
            ],
        )
        assert (
            html_text
            == '<p>Steve Jobs was a human being <sup><a href="http://www.example.com">1</a></sup></p>'
        )

    def test_citation_open_links_new_tab(self):
        md_text = "Steve Jobs was a human being 【1】"
        html_text = md_to_html(
            md_text,
            rust_extensions=[
                CitationExtensionPlugin(
                    citations=[
                        CitationQM(
                            index=1,
                            title="title",
                            source="http://www.example.com",
                            passage="passage",
                            md_offset=29,
                        ),
                    ],
                    open_links_in_new_tab=True,
                ),
                quickmark.Plugin(name="paragraph"),
            ],
        )

        assert (
            html_text
            == '<p>Steve Jobs was a human being <sup><a href="http://www.example.com" target="_blank">1</a></sup></p>'
        )


class TestMathExtension:
    def has_inline_latex(self, text: str) -> bool:
        return '<math display="inline">' in text

    def has_block_latex(self, text: str) -> bool:
        return '<math display="block">' in text

    def has_latex(self, text: str) -> bool:
        return self.has_inline_latex(text) or self.has_block_latex(text)

    def test_no_latex(self):
        text = "Text without dollar sign."
        text = md_to_html(text)
        assert not self.has_latex(text)

    def test_dollar_sign(self):
        text = "A \\$ sign, another \\$ sign."
        text = md_to_html(text)
        assert not self.has_latex(text)

    def test_code_block(self):
        text = "Dollar sign is often use in code ```$1 $2```."
        text = md_to_html(text)
        assert not self.has_latex(text)

    def test_inline_latex_dollar(self):
        text = "An inline latex $a^2$"
        text = md_to_html(text)
        assert self.has_inline_latex(text)

    def test_display_latex_dollar(self):
        text = "A display latex $$a^2$$"
        text = md_to_html(text)
        assert self.has_block_latex(text)

    def test_display_latex_multiline(self):
        text = "$$\na^2\n$$"
        text = md_to_html(text)
        assert self.has_block_latex(text)

    def test_inline_latex(self):
        text = "$y' = mx + b$"
        text = md_to_html(text)
        assert self.has_inline_latex(text)

    def test_inline_latex_full_colon(self):
        text = "P区：$E(x)$"
        text = md_to_html(text)
        assert self.has_inline_latex(text)

    def test_display_latex_dollar_2(self):
        text = "$$y' = mx + b$$"
        text = md_to_html(text)
        assert self.has_block_latex(text)

    def test_display_latex(self):
        text = "$<x>\"y' = 2$"
        expected_html = '<p><math display="inline"><mo><</mo><mi>x</mi><mo>></mo><mi>"</mi><mi>y</mi><mi>′</mi><mo>=</mo><mn>2</mn></math></p>'
        output_html = (md_to_html(text)).replace("\n", "")
        assert output_html == expected_html

    def test_invalid_latex(self):
        text = "invalid latex $a^2^2$"
        text = md_to_html(text)
        assert not self.has_latex(text)

    def test_mix_invalid_latex(self):
        text = "Mix of valid latex $a^2$ and invalid latext $a^2^2$"
        text = md_to_html(text)
        assert self.has_latex(text)

    def test_bold_latex(self):
        text = "**solve for $h$**"
        text = md_to_html(text)
        assert self.has_inline_latex(text)
        assert "<strong>" in text

    def test_bold_dollar_no_latex(self):
        text = "**$5** is less than **$6**"
        text = md_to_html(text)
        assert not self.has_latex(text)

    def test_between_dollar(self):
        # without invalidating if there's an unescaped dollar
        # the very first dollar is a valid opening dollar
        # and the very last is a valid closing dollar
        # so `$5** is less than **$6**. $5 < 6$` ends up being detected as latex
        text = "**$5** is less than **$6**. $5 < 6$"
        text = md_to_html(text)
        bold, latex = text.split(". ")
        assert self.has_latex(latex)
        assert not self.has_latex(bold)

    def test_backslash_n_latex_prefix(self):
        text = "Here are some math symbols: $\\nabla$, $\\notin$, $\\nmid$."
        text = md_to_html(text)
        assert self.has_latex(text)
        assert "<mi>∇</mi" in text  # nabla
        assert "<mo>∉</mo>" in text  # not in
        assert "<mo>∤</mo>" in text  # not mid

    def test_display_math_with_newline(self):
        text = "$$\ne^{-x^{2}}\n$$"
        text = md_to_html(text)
        assert self.has_block_latex(text)
        assert (
            '<p><math display="block"><msup><mi>e</mi><mrow><mi>−</mi><msup><mi>x</mi><mrow><mn>2</mn></mrow></msup></mrow></msup></math></p>'
            in text
        )

    def test_korean_postposition(self):
        text = "$E = mc^2$은 아인슈타인의 방정식입니다."
        text = md_to_html(text)
        assert self.has_inline_latex(text)
        assert (
            '<p><math display="inline"><mi>E</mi><mo>=</mo><mi>m</mi><msup><mi>c</mi><mn>2</mn></msup></math>'
            in text
        )

    def test_ascii_symbol_after_dollar(self):
        """Should not convert to LaTeX if closing dollar followed by ascii symbol"""
        text = "$5 is less than $6!"
        text = md_to_html(text)
        assert not self.has_latex(text)

    def test_triple_apostrophe(self):
        """DoubleSuperscriptsError from mathml extension unless we workaround: https://github.com/roniemartinez/latex2mathml/issues/462"""
        text = "$f(x) = \\sum_{n=0}^{\\infty} \\frac{f^{(n)}(0)}{n!} x^n = f(0) + f'(0)x + \\frac{f''(0)}{2!}x^2 + \\frac{f'''(0)}{3!}x^3 + \\dots$"
        text = md_to_html(text)
        assert self.has_latex(text)

    def test_quadruple_apostrophe(self):
        """DoubleSuperscriptsError from mathml extension unless we workaround: https://github.com/roniemartinez/latex2mathml/issues/462"""
        text = "$f(x) = \\sum_{n=0}^{\\infty} \\frac{f^{(n)}(0)}{n!} x^n = f(0) + f'(0)x + \\frac{f''(0)}{2!}x^2 + \\frac{f''''(0)}{3!}x^3 + \\dots$"
        text = md_to_html(text)
        assert self.has_latex(text)

    def test_quad_error(self):
        """quickmark was not converting this right initially (because of escaping)"""
        text = r"""
        2. **Guaranteeing 20% Expertise**:
            - To **ensure expertise ≥20%**, the servant’s blood quality must satisfy:  
             $$
             \text{Minimum Blood Quality} = \frac{20\%}{0.25} = 80\% \quad (\text{since } 25\% \text{ of } 80\% = 20\%)
             $$
        """.strip()

        text = md_to_html(text)
        assert self.has_latex(text)

    def test_latex_dollar_spacing(self):
        """Test case relating to spacing around dollar signs"""
        text = textwrap.dedent(r"""
            - If each donates **$10**, the total generated would be:
            $ 60,060 \times 10 = \$600,600 $.
           """).strip()

        text = md_to_html(text)
        assert (
            text
            == '<ul>\n<li>If each donates <strong>$10</strong>, the total generated would be:<br />\n<math display="inline"><mn>60,060</mn><mo>×</mo><mn>10</mn><mo>=</mo><mi>$</mi><mn>600,600</mn></math>.</li>\n</ul>'
        )
        assert "<strong>$10</strong>" in text
        assert self.has_latex(text)


class TestCodeExtension:
    def test_file_header(self):
        """check for file header (labels language in FE when rendered)"""
        text = textwrap.dedent(r"""
            ```python
            y = 2
            x = 3
            ```
           """).strip()

        text = md_to_html(
            text, rust_extensions=[InkjetPlugin(pygments_classes=True)]
        )
        assert text.startswith(
            '<div class="codehilite"><span class="filename">Python</span><pre><span></span><code>'
        )
        assert text.endswith("</code></pre></div>")
