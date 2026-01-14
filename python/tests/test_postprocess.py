import html
import itertools
import textwrap

import pytest

from quickmark import CitationQM, md_to_html

from quickmark.postprocess import (
    NodeChunk,
    PrecheckMode,
    DocType,
    complete_backtick,
    convert_citations_to_references,
    extract_citations,
    find_and_reorder_consecutive_citations,
    fix_code_block_with_citation,
    fix_list_spacing_indentation,
    get_excerpt_and_citation,
    get_tag_placeholder,
    guard_tag,
    markdown_to_html,
    nest_list_with_4_spaces,
    normalize_codeblocks,
    postprocess_citation,
    protect_tags,
    regex_precheck,
    remove_think_details_tags,
    unescape_br_in_table,
    unescape_tags,
)

DROPDOWN_TAGS = ("<summary>", "</summary>", "<details>", "</details>")


class TestExtractCitations:
    def test_no_citations_in_text(self):
        answer = "This is a text without citation."
        passages = []
        new_answer, citations, _ = extract_citations(answer, passages)
        assert (new_answer, citations) == (answer, passages)

    def test_out_of_index_citation(self):
        answer = "Out of index claim【10】."
        passages = [NodeChunk(source="", title="", text="")]

        expected_answer = "Out of index claim."
        expected_citations = []
        new_answer, citations, _ = extract_citations(answer, passages)
        assert (new_answer, citations) == (expected_answer, expected_citations)

    def test_zero_index_citation(self):
        answer = "zero index claim【0】."
        passages = [NodeChunk(source="", title="", text="")]

        expected_answer = "zero index claim."
        expected_citations = []
        new_answer, citations, _ = extract_citations(answer, passages)
        assert (new_answer, citations) == (expected_answer, expected_citations)

    def test_same_source_same_index(self):
        # should have same index
        answer = "Different passages【1】, from the same source【2】."
        passages = [
            NodeChunk("s1", "t1", "t1 chunk1"),
            NodeChunk("s1", "t1", "t1 chunk5"),
        ]

        expected_answer = "Different passages【1】, from the same source【1】."
        expected_citations = [
            CitationQM(
                index=1,
                title="t1",
                source="s1",
                passage="t1 chunk1",
                md_offset=18,
                passage_length=9,
            ),
            CitationQM(
                index=1,
                title="t1",
                source="s1",
                passage="t1 chunk5",
                md_offset=43,
                passage_length=9,
            ),
        ]
        extract_citations(answer, passages)
        new_answer, citations, _ = extract_citations(answer, passages)
        assert (new_answer, citations) == (expected_answer, expected_citations)

    def test_same_source_on_same_statement(self):
        # remove repeating index until we add 1a 1b.
        answer = "Different passages, from the same source【1】【3】【2】."
        passages = [
            NodeChunk("s1", "t1", "t1 chunk1"),
            NodeChunk("s1", "t1", "t1 chunk5"),
            NodeChunk("s2", "t2", "t2 chunk1"),
        ]

        expected_answer = "Different passages, from the same source【1】【2】."
        expected_citations = [
            CitationQM(
                index=1,
                title="t1",
                source="s1",
                passage="t1 chunk1",
                md_offset=40,
                passage_length=9,
            ),
            CitationQM(
                index=2,
                title="t2",
                source="s2",
                passage="t2 chunk1",
                md_offset=43,
                passage_length=9,
            ),
        ]
        new_answer, citations, _ = extract_citations(answer, passages)
        assert (new_answer, citations) == (expected_answer, expected_citations)

    def test_same_source_separate_by_invalid_index(self):
        # remove repeating index until we add 1a 1b.
        answer = "Different passages, from the same source【1】【13】【2】."
        passages = [
            NodeChunk("s1", "t1", "t1 chunk1"),
            NodeChunk("s1", "t1", "t1 chunk5"),
        ]

        expected_answer = "Different passages, from the same source【1】."
        expected_citations = [
            CitationQM(
                index=1,
                title="t1",
                source="s1",
                passage="t1 chunk1",
                md_offset=40,
                passage_length=9,
            ),
        ]
        new_answer, citations, _ = extract_citations(answer, passages)
        assert (new_answer, citations) == (expected_answer, expected_citations)

    def test_truncate_long_citations(self):
        # remove repeating index until we add 1a 1b.
        answer = "Different passages, from the same source【1】【2】【3】."
        passages = [
            NodeChunk("s1", "t1", "t1 chunk1"),
            NodeChunk("s2", "t2", "t2 chunk1"),
            NodeChunk("s3", "t3", "t3 chunk1"),
        ]

        expected_answer = "Different passages, from the same source【1】【2】."
        expected_citations = [
            CitationQM(
                index=1,
                title="t1",
                source="s1",
                passage="t1 chunk1",
                md_offset=40,
                passage_length=9,
            ),
            CitationQM(
                index=2,
                title="t2",
                source="s2",
                passage="t2 chunk1",
                md_offset=43,
                passage_length=9,
            ),
        ]
        new_answer, citations, _ = extract_citations(answer, passages)
        assert (new_answer, citations) == (expected_answer, expected_citations)

    def test_rolling_offset(self):
        passages = [NodeChunk(f"s{i}", f"t{i}", "text") for i in range(1, 12)]
        answer = "This is a statement. 【11】 This is another. 【4】"
        answer, _, _ = extract_citations(answer, passages)

        expected_answer = "This is a statement. 【1】 This is another. 【2】"
        assert answer == expected_answer

    def test_md_offset(self):
        passages = [NodeChunk(f"s{i}", f"t{i}", "text") for i in range(1, 12)]
        answer = "This is a statement. 【11】【1】 This is another. 【4】"
        answer, citations, _ = extract_citations(answer, passages)

        for citation in citations:
            citaton_start = citation.md_offset
            citation_end = citaton_start + len(citation.to_md())
            assert answer[citaton_start:citation_end] == citation.to_md()


class TestCitationConversion:
    def test_convert_empty_citations(self):
        citations = []
        search_results = [
            NodeChunk(
                doc_type=DocType.WEB,
                title="t1",
                source="https://sample.com",
                text="passage",
            )
        ]
        assert convert_citations_to_references(citations, search_results) == []

    def test_convert_empty_search_results(self):
        citations = [
            CitationQM(
                index=1, title="t1", source="u1", passage="passage", md_offset=5
            )
        ]
        assert (
            convert_citations_to_references(citations, extracted_documents=[])
            == []
        )

    def test_convert_user_uploaded_document(self):
        citations = [
            CitationQM(
                index=1,
                title="t1",
                source="sample.pdf",
                passage="passage",
                md_offset=5,
            )
        ]
        extracted_documents = [
            NodeChunk(
                doc_type=DocType.PDF,
                title="t1",
                source="sample.pdf",
                text="passage",
            )
        ]
        references = convert_citations_to_references(
            citations, extracted_documents
        )
        assert len(references) == 1
        assert references[0].source == "sample.pdf"
        assert references[0].title == "t1"
        assert references[0].passages == ["passage"]

    def test_excerpt_citation_mapping(self):
        text = """\
        The capacity of the orchestra level of the Hanna Theatre in Cleveland, Ohio, before its renovation was **827 seats**.

        The Hanna Theatre opened in March 1921 as part of the Hanna Building in downtown Cleveland, built by industrialist and publisher Daniel Rhodes Hanna 【1】. The theatre's original configuration featured the orchestra level with 827 seats arranged in 24 rows, while the upper deck (balcony) held 570 seats 【2】. 

        The complete original seating breakdown included:
        - Orchestra level: 827 seats
        - Balcony: 570 seats  
        - Four rows in the mezzanine
        - Ten rows in the upper balcony
        - Box seats

        This brought the theatre's total original capacity to either 1,400 or 1,421 seats, depending on the source 【1】【2】. """
        citations = [
            CitationQM(
                index=1,
                title="Hanna Theatre, Cleveland",
                source="",
                passage="The 1,400-seat theatre was built with 827 seats at orchestra (main floor) level and 570 seats in the balcony.",
                md_offset=268,
            ),
            CitationQM(
                index=2,
                title="Hanna Theatre",
                source="",
                passage="The orchestra level consisted of 827 seats arranged in 24 rows, and the upper deck held 570 seats.",
                md_offset=421,
            ),
            CitationQM(
                index=1,
                title="Hanna Theatre, Cleveland",
                source="",
                passage="The 1,400-seat theatre was built with 827 seats at orchestra (main floor) level and 570 seats in the balcony.",
                md_offset=711,
            ),
            CitationQM(
                index=2,
                title="Hanna Theatre",
                source="",
                passage="The orchestra level consisted of 827 seats arranged in 24 rows, and the upper deck held 570 seats.",
                md_offset=714,
            ),
        ]
        excerpt_bucket = get_excerpt_and_citation(
            textwrap.dedent(text), citations
        )
        assert len(excerpt_bucket) == 3, (
            f"There are more items than expected, {len(excerpt_bucket)}"
        )
        for excerpt in excerpt_bucket:
            assert "【" not in excerpt and "】" not in excerpt, (
                f"Excerpt include reference marks: {excerpt}"
            )


# These tests mirror mother.tests.test_postprocess.TestExtractCitations
# They are fairly comprehensive for testing citations in different scenarios.
# There are some tests that are redundant, but they are kept for consistency.
class TestEncodeCitations:
    def run_test(
        self,
        passages: list[NodeChunk],
        markdown: str,
        expected_html: str,
    ):
        completion, citations, _ = postprocess_citation(
            markdown, passages=passages
        )
        output_html = markdown_to_html(completion, citations)
        assert textwrap.dedent(expected_html) in textwrap.dedent(output_html)

    def test_no_citations_in_text(self):
        passages: list[NodeChunk] = []
        markdown = "This is a text without citation."
        expected_html = markdown
        self.run_test(passages, markdown, expected_html)

    def test_out_of_index_citation(self):
        passages: list[NodeChunk] = [
            NodeChunk(source="s1", title="t1", text="text1")
        ]
        markdown = "Out of index claim【10】."
        expected_html = "Out of index claim"
        self.run_test(passages, markdown, expected_html)

    def test_zero_index_citation(self):
        passages: list[NodeChunk] = [
            NodeChunk(source="s1", title="t1", text="text1")
        ]
        markdown = "zero index claim【0】."
        expected_html = "zero index claim."
        self.run_test(passages, markdown, expected_html)

    def test_same_source_same_index(self):
        passages: list[NodeChunk] = [
            NodeChunk(source="s1", title="t1", text="t1 chunk1"),
            NodeChunk(source="s1", title="t1", text="t1 chunk5"),
        ]
        markdown = "Different passages, from the same source【1】【2】."
        expected_html = "<p>Different passages, from the same source<sup><a>1</a></sup>.</p>"
        self.run_test(passages, markdown, expected_html)

    def test_same_source_on_same_statement(self):
        passages: list[NodeChunk] = [
            NodeChunk(source="s1", title="t1", text="t1 chunk1"),
            NodeChunk(source="s2", title="t2", text="t2 chunk1"),
        ]
        markdown = "Different passages, from the same source【1】【2】."
        expected_html = "<p>Different passages, from the same source<sup><a>1</a></sup><sup><a>2</a></sup>.</p>"
        self.run_test(passages, markdown, expected_html)

    def test_same_source_separate_by_invalid_index(self):
        passages: list[NodeChunk] = [
            NodeChunk(source="s1", title="t1", text="t1 chunk1"),
            NodeChunk(source="s1", title="t1", text="t1 chunk5"),
        ]
        markdown = "Different passages, from the same source【1】【13】【2】."
        expected_html = "<p>Different passages, from the same source<sup><a>1</a></sup>.</p>"
        self.run_test(passages, markdown, expected_html)

    def test_truncate_long_citations(
        self,
    ):
        passages: list[NodeChunk] = [
            NodeChunk(source="s1", title="t1", text="t1 chunk1"),
            NodeChunk(source="s2", title="t2", text="t2 chunk1"),
            NodeChunk(source="s3", title="t3", text="t3 chunk1"),
        ]
        markdown = "Different passages, from the same source【1】【2】【3】."
        expected_html = "<p>Different passages, from the same source<sup><a>1</a></sup><sup><a>2</a></sup>.</p>"
        self.run_test(passages, markdown, expected_html)

    def test_rolling_offset(self):
        passages: list[NodeChunk] = [
            NodeChunk(source="s1", title="t1", text="t1 chunk1"),
            NodeChunk(source="s1", title="t1", text="t1 chunk5"),
        ]
        markdown = "This is a statement. 【11】 This is another. 【4】"
        expected_html = "This is a statement.  This is another."
        self.run_test(passages, markdown, expected_html)

    def test_md_offset(self):
        passages: list[NodeChunk] = [
            NodeChunk(source="s1", title="t1", text="t1 chunk1"),
            NodeChunk(source="s2", title="t2", text="t2 chunk1"),
            NodeChunk(source="s3", title="t3", text="t3 chunk1"),
        ]
        markdown = "This is a statement. 【11】【1】 This is another. 【4】"
        expected_html = (
            "This is a statement. <sup><a>1</a></sup> This is another."
        )
        self.run_test(passages, markdown, expected_html)


@regex_precheck("check", mode=PrecheckMode.ANY)
def my_func_any(text):
    return f"Processed {text}"


@regex_precheck("check", mode=PrecheckMode.ALL)
def my_func_all(text):
    return f"Processed {text}"


@regex_precheck(("check", "this"), mode=PrecheckMode.ANY)
def my_generator_func_any(text):
    yield f"Processed {text}"


@regex_precheck(("check", "this"), mode=PrecheckMode.ALL)
def my_generator_func_all(text):
    yield f"Processed {text}"


class TestRegexPrecheck:
    def test_func_any_skip(self):
        assert my_func_any("random text") == "random text"

    def test_func_any_process(self):
        assert my_func_any("check this out") == "Processed check this out"

    def test_func_all_skip(self):
        assert my_func_all("random text") == "random text"

    def test_func_all_process(self):
        assert my_func_all("check this out") == "Processed check this out"

    def test_generator_func_any_skip(self):
        assert list(my_generator_func_any("random text")) == []

    def test_generator_func_any_process(self):
        assert list(my_generator_func_any("check this out")) == [
            "Processed check this out"
        ]

    def test_generator_func_all_skip_one_missing(self):
        assert list(my_generator_func_all("check out")) == []

    def test_generator_func_all_skip_both_missing(self):
        assert list(my_generator_func_all("random text")) == []

    def test_generator_func_all_process(self):
        assert list(my_generator_func_all("check this out")) == [
            "Processed check this out"
        ]


class TestNestedList:
    def test_nested_list(self):
        text = textwrap.dedent(
            """\
        - list
          - sublist
        """
        )

        expected = textwrap.dedent(
            """\
        - list
            - sublist
        """
        )
        assert nest_list_with_4_spaces(text) == expected

    def test_text_without_list(self):
        text = "Some text without list"
        assert nest_list_with_4_spaces(text) == text

    def test_code_block(self):
        text = textwrap.dedent(
            """\
        ```
        - list
          - sublist
        ```
        """
        )

        assert nest_list_with_4_spaces(text) == text

    def test_ordered_list(self):
        text = textwrap.dedent(
            """\
        1. list 1
          1. sublist 1
          2. sublist 2
        2. list 2
          1. sublist 1
            - unordered sublist item
        """
        )

        expected = textwrap.dedent(
            """\
        1. list 1
            1. sublist 1
            2. sublist 2
        2. list 2
            1. sublist 1
                - unordered sublist item
        """
        )
        assert nest_list_with_4_spaces(text) == expected

    def test_already_using_4_spaces_list(self):
        text = textwrap.dedent(
            """\
        1. list 1
            1. sublist 1
                2. sublist 2
        2. list 2
            1. sublist 1
                - unordered sublist item
        """
        )
        assert nest_list_with_4_spaces(text) == text

    def test_already_using_3_spaces_list(self):
        text = textwrap.dedent(
            """\
        1. list 1
           1. sublist 1
              2. sublist 2
        2. list 2
           1. sublist 1
              - unordered sublist item
        """
        )
        expected = textwrap.dedent(
            """\
        1. list 1
            1. sublist 1
                2. sublist 2
        2. list 2
            1. sublist 1
                - unordered sublist item
        """
        )

        assert nest_list_with_4_spaces(text) == expected

    def test_tab_indented_nested_list(self):
        """Test that tab-indented nested list items are preserved, not skipped.

        This tests the bug fix where lines starting with tabs were being completely
        removed instead of having their tabs converted to spaces.
        """
        text = "- **Features**:\n\t- Offers food logging\n\t- Includes different styles\n- **Pricing**:\n\t- Monthly: $11.99"

        expected = "- **Features**:\n    - Offers food logging\n    - Includes different styles\n- **Pricing**:\n    - Monthly: $11.99"

        result = nest_list_with_4_spaces(text)
        assert result == expected

        # Check that no content was lost
        assert "Offers food logging" in result
        assert "Monthly: $11.99" in result


def test_unordered_list_become_heading():
    """Test text don't wrap in h2 tag when streaming unordered list"""
    text = "- takeaway 1. \n-"
    output_html = markdown_to_html(text)
    assert "<h2>" not in output_html


class TestMathExtension:
    def has_inline_latex(self, text: str) -> bool:
        return (
            '<math xmlns="http://www.w3.org/1998/Math/MathML" display="inline">'
            in text
            or '<math display="inline">' in text
        )

    def has_block_latex(self, text: str) -> bool:
        return (
            '<math xmlns="http://www.w3.org/1998/Math/MathML" display="block">'
            in text
            or '<math display="block">' in text
        )

    def has_latex(self, text: str) -> bool:
        return self.has_inline_latex(text) or self.has_block_latex(text)

    def test_no_latex(
        self,
    ):
        text = "Text without dollar sign."
        text = md_to_html(text)
        assert not self.has_latex(text)

    def test_dollar_sign(
        self,
    ):
        text = "A \\$ sign, another \\$ sign."
        text = md_to_html(text)
        assert not self.has_latex(text)

    def test_code_block(
        self,
    ):
        text = "Dollar sign is often use in code ```$1 $2```."
        text = md_to_html(text)
        assert not self.has_latex(text)

    def test_inline_latex_dollar(
        self,
    ):
        text = "An inline latex $a^2$"
        text = md_to_html(text)
        assert self.has_inline_latex(text)

    def test_display_latex_dollar(
        self,
    ):
        text = "A display latex $$a^2$$"
        text = md_to_html(text)
        assert self.has_block_latex(text)

    def test_display_latex_multiline(
        self,
    ):
        text = "$$\na^2\n$$"
        text = md_to_html(text)
        assert self.has_block_latex(text)

    # NOTE(Rehan): commented these out, haven't supported in quickmark since the models don't use this syntax
    # def test_display_latex_paren(self, ):
    #     text = "\\[\\n F = ma \\n\\]"
    #     text = md_to_html( text)
    #     assert self.has_block_latex(text)

    # def test_inline_latex_parent(self, ):
    #     text = "Inline latex with \\(a^2 + b^2 = c^2\\)"
    #     text = md_to_html( text)
    #     assert self.has_inline_latex(text)

    def test_inline_latex(
        self,
    ):
        text = "$y' = mx + b$"
        text = md_to_html(text)
        assert self.has_inline_latex(text)

    def test_inline_latex_full_colon(
        self,
    ):
        text = "P区：$E(x)$"
        text = md_to_html(text)
        assert self.has_inline_latex(text)

    def test_display_latex_dollar_2(
        self,
    ):
        text = "$$y' = mx + b$$"
        text = md_to_html(text)
        assert self.has_block_latex(text)

    def test_display_latex(
        self,
    ):
        text = "$<x>\"y' = 2$"
        expected_html = '<p><span><math xmlns="http://www.w3.org/1998/Math/MathML" display="inline"><mrow><mo>&#x0003C;</mo><mi>x</mi><mo>&#x0003E;</mo><mi>"</mi><msup><mi>y</mi><mi>&#x02032;</mi></msup><mo>&#x0003D;</mo><mn>2</mn></mrow></math></span></p>'
        expected_html_quickmark = '<p><math display="inline"><mo><</mo><mi>x</mi><mo>></mo><mi>"</mi><mi>y</mi><mi>′</mi><mo>=</mo><mn>2</mn></math></p>'
        output_html = (md_to_html(text)).replace("\n", "")
        assert output_html in (expected_html, expected_html_quickmark)

    def test_invalid_latex(
        self,
    ):
        text = "invalid latex $a^2^2$"
        text = md_to_html(text)
        assert not self.has_latex(text)

    def test_mix_invalid_latex(
        self,
    ):
        text = "Mix of valid latex $a^2$ and invalid latext $a^2^2$"
        text = md_to_html(text)
        assert self.has_latex(text)

    def test_bold_latex(
        self,
    ):
        text = "**solve for $h$**"
        text = md_to_html(text)
        assert self.has_inline_latex(text)
        assert "<strong>" in text

    def test_bold_dollar_no_latex(
        self,
    ):
        text = "**$5** is less than **$6**"
        text = md_to_html(text)
        assert not self.has_latex(text)

    def test_between_dollar(
        self,
    ):
        # without invalidating if there's an unescaped dollar
        # the very first dollar is a valid opening dollar
        # and the very last is a valid closing dollar
        # so `$5** is less than **$6**. $5 < 6$` ends up being detected as latex
        text = "**$5** is less than **$6**. $5 < 6$"
        text = md_to_html(text)
        bold, latex = text.split(". ")
        assert self.has_latex(latex)
        assert not self.has_latex(bold)

    def test_backslash_n_latex_prefix(
        self,
    ):
        text = "Here are some math symbols: $\\nabla$, $\\notin$, $\\nmid$."
        text = md_to_html(text)
        assert self.has_latex(text)
        assert "<mo>&#x02207;</mo>" in text or "<mi>∇</mi" in text  # nabla
        assert "<mo>&#x02209;</mo>" in text or "<mo>∉</mo>" in text  # not in
        assert "<mo>&#x02224;</mo>" in text or "<mo>∤</mo>" in text  # not mid

    def test_display_math_with_newline(
        self,
    ):
        text = "$$\ne^{-x^{2}}\n$$"
        text = md_to_html(text)
        assert self.has_block_latex(text)
        assert (
            '<math xmlns="http://www.w3.org/1998/Math/MathML" display="block"><mrow><msup><mi>e</mi><mrow><mo>&#x02212;</mo><msup><mi>x</mi><mrow><mn>2</mn></mrow></msup></mrow></msup></mrow></math>'
            in text
            or '<p><math display="block"><msup><mi>e</mi><mrow><mi>−</mi><msup><mi>x</mi><mrow><mn>2</mn></mrow></msup></mrow></msup></math></p>'
            in text
        )

    def test_korean_postposition(
        self,
    ):
        text = "$E = mc^2$은 아인슈타인의 방정식입니다."
        text = md_to_html(text)
        assert self.has_inline_latex(text)
        assert (
            '<math xmlns="http://www.w3.org/1998/Math/MathML" display="inline"><mrow><mi>E</mi><mo>&#x0003D;</mo><mi>m</mi><msup><mi>c</mi><mn>2</mn></msup></mrow></math>'
            in text
            or '<p><math display="inline"><mi>E</mi><mo>=</mo><mi>m</mi><msup><mi>c</mi><mn>2</mn></msup></math>'
            in text
        )

    def test_ascii_symbol_after_dollar(
        self,
    ):
        """Should not convert to LaTeX if closing dollar followed by ascii symbol"""
        text = "$5 is less than $6!"
        text = md_to_html(text)
        assert not self.has_latex(text)

    def test_triple_apostrophe(
        self,
    ):
        """DoubleSuperscriptsError from mathml extension unless we workaround: https://github.com/roniemartinez/latex2mathml/issues/462"""
        text = "$f(x) = \\sum_{n=0}^{\\infty} \\frac{f^{(n)}(0)}{n!} x^n = f(0) + f'(0)x + \\frac{f''(0)}{2!}x^2 + \\frac{f'''(0)}{3!}x^3 + \\dots$"
        text = md_to_html(text)
        assert self.has_latex(text)

    def test_quadruple_apostrophe(
        self,
    ):
        """DoubleSuperscriptsError from mathml extension unless we workaround: https://github.com/roniemartinez/latex2mathml/issues/462"""
        text = "$f(x) = \\sum_{n=0}^{\\infty} \\frac{f^{(n)}(0)}{n!} x^n = f(0) + f'(0)x + \\frac{f''(0)}{2!}x^2 + \\frac{f''''(0)}{3!}x^3 + \\dots$"
        text = md_to_html(text)
        assert self.has_latex(text)

    def test_latex_dollar_spacing(
        self,
    ):
        """Test case relating to spacing around dollar signs"""
        text = textwrap.dedent(r"""
            - If each donates **$10**, the total generated would be:
            $ 60,060 \times 10 = \$600,600 $.
           """).strip()

        text = md_to_html(text)
        assert "<strong>$10</strong>" in text
        assert self.has_latex(text)


class TestContactInfoExtension:
    def test_plain_phone_number(
        self,
    ):
        text = "Contact me at 123-456-7890."
        output_html = md_to_html(text)
        output_html = output_html.replace("\n", "")
        assert '<a href="tel:1234567890">123-456-7890</a>' in output_html

    def test_phone_number_with_parentheses(
        self,
    ):
        text = "For general ticket sales and inquiries: (800)-515-2171."
        output_html = md_to_html(text)
        output_html = output_html.replace("\n", "")
        assert ': <a href="tel:8005152171">(800)-515-2171</a>' in output_html

    def test_phone_number_with_double_parentheses(
        self,
    ):
        text = "Hotline For Canada: ((877)-529-7746)."
        output_html = md_to_html(text)
        output_html = output_html.replace("\n", "")
        assert ': (<a href="tel:8775297746">(877)-529-7746</a>)' in output_html

    def test_phone_number_with_dots(
        self,
    ):
        text = "Phone number can also be formatted with dots: 123.456.7890."
        output_html = md_to_html(text)
        output_html = output_html.replace("\n", "")
        assert ': <a href="tel:1234567890">123.456.7890</a>' in output_html

    def test_phone_number_with_spaces(
        self,
    ):
        text = "Contact me at +12 123-456-7890 or email me at john.doe@amazon.co.jp"
        output_html = md_to_html(text)
        output_html = output_html.replace("\n", "")
        assert (
            'Contact me at <a href="tel:+121234567890">+12 123-456-7890</a>'
            in output_html
        )

    def test_phone_number_with_email(
        self,
    ):
        text = "You can reach the support team at 1-800-123-4567 or email them at support@kaggle.com."
        output_html = md_to_html(text)
        output_html = output_html.replace("\n", "")
        assert '<a href="tel:18001234567">1-800-123-4567</a>' in output_html
        assert (
            '<a href="mailto:support@kaggle.com">support@kaggle.com</a>'
            in output_html
        )

    def test_phone_number_preceded_by_open_parenthesis(
        self,
    ):
        text = "(123-456-7890"
        output_html = md_to_html(text)
        output_html = output_html.replace("\n", "")
        assert '<a href="tel:1234567890">123-456-7890</a>' in output_html

    def test_ignore_phone_number_preceded_by_non_whitespace_char(
        self,
    ):
        text = "This is a phone number:123-456-7890."
        output_html = md_to_html(text)
        output_html = output_html.replace("\n", "")
        assert "tel:" not in output_html

    def test_ignore_phone_number_in_url(
        self,
    ):
        url = "https://www.example.com/p/Multi-Purpose-Synthetic-Oil-Bottle-PTFE-ISO-100-150-51008/304673224"
        text = f"This does not contain phone number: {url}."
        output_html = md_to_html(text)
        output_html = output_html.replace("\n", "")
        assert "tel:" not in output_html

    def test_ignore_latex(
        self,
    ):
        text = "This may look like a phone number $123.4567890$ but it is not."
        output_html = md_to_html(text)
        output_html = output_html.replace("\n", "")
        assert (
            '<span><math xmlns="http://www.w3.org/1998/Math/MathML" display="inline">'
            in output_html
            or '<math display="inline"><mn>123.4567890</mn></math>'
            in output_html
        )
        assert '<a href="tel:' not in output_html

    def test_ignore_url(
        self,
    ):
        text = "This does not contain a phone number: [https://evolution-outreach.biomedcentral.com/articles/10.1007/s12052-010-0226-0](https://evolution-outreach.biomedcentral.com/articles/10.1007/s12052-010-0226-0)."
        output_html = md_to_html(text)
        output_html = output_html.replace("\n", "")
        assert '<a href="https://' in output_html
        assert '<a href="tel:' not in output_html

    def test_email_in_url(
        self,
    ):
        text = "This is a link with an email-like string in url: https://www.postgresql.org/message-id/40FB2AE5907F9743A593A85015F157BF060BB3A1@ARG-EXVS03.corp.argushealth.com"
        output_html = md_to_html(text)
        output_html = output_html.replace("\n", "")
        assert '<a href="mailto' not in output_html


def test_code_block_with_citation():
    text = textwrap.dedent("""
    ```python
    print("this is some code")
    ``` 【1】
    """)
    fixed_text = fix_code_block_with_citation(text)
    assert not any(
        "```" in line and "【" in line for line in fixed_text.split("\n")
    )


def test_code_block_with_citation_after():
    text = textwrap.dedent("""
    ```python
    print("this is some code")
    ```
     【1】
    """)
    fixed_text = fix_code_block_with_citation(text)
    assert fixed_text == text


def test_misindented_code_block():
    text = textwrap.dedent("""
    - list item
        - this is a list subitem
        ```python
    print("this is a misindented codeblock")
    ```
    """)
    normalized = textwrap.dedent("""
    - list item
        - this is a list subitem
    ```python
    print("this is a misindented codeblock")
    ```
    """)
    fixed_text = normalize_codeblocks(text)
    assert fixed_text == normalized


def test_fix_list_indentation_properly_formatted():
    text = textwrap.dedent("""
    # 1. This is properly formatted, doesn't need changing
    - A level 1 bullet under a header renders fine
    - We put a newline indiscriminately between list and non list, but it doesn't change end HTML
    """)
    fixed = textwrap.dedent("""
    # 1. This is properly formatted, doesn't need changing

    - A level 1 bullet under a header renders fine
    - We put a newline indiscriminately between list and non list, but it doesn't change end HTML
    """)
    assert fix_list_spacing_indentation(text) == fixed


def test_fix_list_indentation_improperly_formatted():
    text = textwrap.dedent("""
    # 1. This is not properly formatted
        - This indentation makes it render as a codeblock, not a bullet
        - since there is no level 1 bullet (header doesn't count) 
    """).strip()
    fixed = textwrap.dedent("""
    # 1. This is not properly formatted

    - This indentation makes it render as a codeblock, not a bullet
    - since there is no level 1 bullet (header doesn't count) 
    """).strip()
    assert fix_list_spacing_indentation(text) == fixed


def test_keep_summary_tag():
    md_text = "<details><summary>Summary</summary>Long details here</details>"
    html_text = markdown_to_html(md_text, keep_summary_tag=True)

    for tag in DROPDOWN_TAGS:
        assert tag in html_text


class TestRustPanics:
    def test_no_fail_panic(self, ctx):
        # NOTE (matt): the rust parser can fail on single backticks (2025-02)
        broken_text = "Look at ```formatted code```. This is `also correct`. But `this is not correct."
        try:
            html_text = markdown_to_html(broken_text)
            assert isinstance(html_text, str) and len(html_text) > 0
        except Exception as e:
            pytest.fail(f"An exception was raised: {e}")


class TestLinkProcessor:
    def test_normal_link_unaffected(self, ctx):
        md_text = "This is an [example](https://www.example.com)."
        html_text = markdown_to_html(md_text)
        assert '<a href="https://www.example.com"' in html_text

    def test_codeblock(self, ctx):
        md_text = "`[example](https://www.example.com).`"
        html_text = markdown_to_html(md_text)
        assert '<a href="https://www.example.com"' not in html_text

    def test_image(self, ctx):
        md_text = "This is an ![image](https://www.example.com/image.png)."
        html_text = markdown_to_html(md_text)
        assert "<img" in html_text

    def test_open_in_new_tab(self, ctx):
        md_text = "This is an [link](https://www.example.com/link)."
        html_text = markdown_to_html(md_text, open_links_in_new_tab=True)
        assert 'target="_blank"' in html_text

    def test_square_brackets_link_text(self, ctx):
        md_text = "This is an [link and these are [square brackets]](https://www.example.com/link)."
        html_text = markdown_to_html(md_text)
        assert '<a href="https://www.example.com/link"' in html_text
        assert "link and these are [square brackets]" in html_text


def test_remove_link_to_be_proxied():
    bucket_url = "https://storage.googleapis.com/kagi/test.mp3"
    md_text = f"You can listen to the audio [here]({bucket_url})"
    html_text = markdown_to_html(md_text, remove_links_to_be_proxied=True)
    assert bucket_url not in html_text
    assert "You can listen to the audio here" in html_text


def test_remove_image_to_be_proxied():
    bucket_url = "https://storage.googleapis.com/kagi/image.png"
    md_text = f"Here is the image ![image]({bucket_url})"
    html_text = markdown_to_html(md_text, remove_links_to_be_proxied=True)
    assert bucket_url not in html_text
    assert "Here is the image" in html_text


def test_remove_image_result_to_be_proxied():
    image_url = "https://example.com/image.png"
    md_text = f"Here is the image ![image]({image_url})"
    html_text = markdown_to_html(md_text, remove_links_to_be_proxied=True)
    assert image_url not in html_text
    assert "Here is the image" in html_text


def test_partial_link_removed():
    partial_bucket_url = "https://storage.googleapis.com/kagi/my_secret_bucket"
    md_text = f"You can listen to the audio [here]({partial_bucket_url}"
    html_text = markdown_to_html(md_text, remove_links_to_be_proxied=True)
    assert partial_bucket_url not in html_text
    assert "You can listen to the audio here" in html_text


def test_escape_br_in_table():
    text = textwrap.dedent("""
        Some random text with &lt;br&gt; tags. This is the first line.&lt;br&gt;This is the second line.&lt;br&gt;And here's a third line for good measure.

        | Column 1 | Column 2 | Column 3 |
        |----------|----------|----------|
        | First cell&lt;br&gt;with multiple&lt;br&gt;lines | Another cell&lt;br&gt;spanning&lt;br&gt;multiple lines | Third cell&lt;br&gt;also with&lt;br&gt;line breaks |
        | More content&lt;br&gt;in this cell | Second row&lt;br&gt;second column | Last cell&lt;br&gt;of this row |

        Here are some inline codeblocks containing just ```<br>``` tags:

        This is text with a ```<br>``` tag in the middle.

        Here's another example with ```<br>``` by itself.

        And one more inline code: ```<br>```
    """).strip()

    output = unescape_br_in_table(text)

    output_lines = output.split("\n")

    regular_text = output_lines[0]
    table_text = "\n".join([line for line in output_lines if "|" in line])
    code_text = "\n".join([line for line in output_lines if "`" in line])

    assert html.escape("<br>") in regular_text
    assert "<br>" in table_text
    assert "<br>" in code_text


def test_unescape_tags():
    open_tag = "<tag>"
    close_tag = "</tag>"
    text = textwrap.dedent(f"""
        {html.escape(open_tag)} we want escaped
        this too: {html.escape(close_tag)}

        ```
        code here, no touching these: {html.escape(open_tag)}, {html.escape(close_tag)}
        ```
    """).strip()

    text = unescape_tags(text, ["<tag>", "</tag>"])
    non_code, _, code = text.partition("```")

    assert open_tag in non_code
    assert close_tag in non_code

    assert html.escape(open_tag) in code
    assert html.escape(close_tag) in code


class TestThinkTags:
    def test_guard_tag_and_remove_think_integration(self):
        test_cases = [
            (
                "<think>\nLet me analyze this step by step\n</think>Here's the answer",
                "Here's the answer",
            ),
            (
                "<think>\nHere is the code\n```python\nprint('Hello, world!')\n```\n</think>Here's the answer",
                "Here's the answer",
            ),
            (
                "<think>First analysis</think>So this should not be removed",
                "<think>First analysis</think>So this should not be removed",
            ),
            ("<think>\nOnly thinking here\n</think>", "."),
            ("Just a regular response", "Just a regular response"),
            ("<think>\nIncomplete thinking", "."),
        ]

        for input_content, expected_final in test_cases:
            with_details = guard_tag("think", input_content)
            final_content = remove_think_details_tags(with_details)
            assert final_content == expected_final, (
                f"Failed for input: {input_content}, expected: {expected_final}, got: {final_content}"
            )


def test_protect_tags():
    text = "<details><summary>Thinking</summary>\n\nLet me think\n\n</details>\n\nOk I'm done thinking, here is how to cure cancer: An error occurred"
    tags = list(DROPDOWN_TAGS)
    with protect_tags(text, tags) as container:
        assert all(get_tag_placeholder(tag) in container.text for tag in tags)

        container.text = markdown.markdown(container.text)

    assert not any(get_tag_placeholder(tag) in container.text for tag in tags)

    assert (
        container.text
        == "<details><summary>Thinking</summary>\n<p>Let me think</p>\n</details>\n<p>Ok I'm done thinking, here is how to cure cancer: An error occurred</p>"
    )


def test_protect_tags_avoid_code():
    text = textwrap.dedent("""
        <summary>This is not code</summary>
        ```
        <summary>This is code</summary>
        ```
    """).strip()
    tags = ["<summary>", "</summary>"]
    with protect_tags(text, tags) as container:
        non_code, code, *_ = container.text.split("```")
        assert all(get_tag_placeholder(tag) in non_code for tag in tags)
        assert not any(get_tag_placeholder(tag) in code for tag in tags)

        container.text = markdown.markdown(container.text)

    assert not any(get_tag_placeholder(tag) in container.text for tag in tags)


def test_thinking_complete_backticks():
    """
    We don't want to complete unescaped standalone backticks in thinking.
    In thinking, a model (grok 3 mini) may use backticks incorrectly (when thinking about using them for the codeblock)
    This leaves the unescaped standalone backticks verbatim in the thinking block.
    """

    text = "<details><summary>Thinking</summary>\n\nLet me think, I need to use ```html to format this in codeblocks.\n\n</details>\n\nOk I'm done thinking, here is a codeblock: ```code and stuff```"
    text = complete_backtick(text)
    thinking, response = text.split("</details>")
    assert thinking.count("```") == 1
    assert response.count("```") == 2


class TestReorderConsecutiveCitations:
    @pytest.mark.parametrize(
        "text,citation_indexes",
        [
            ("First. 【11】【3】【4】Second. 【7】【2】", [11, 3, 4, 7, 2]),
            (
                "Michael Portnoy was born in New York【41】【9】【57】【67】【61】【62】【30】.",
                [41, 9, 57, 67, 61, 62, 30],
            ),
        ],
    )
    def test_no_reorder(self, text, citation_indexes):
        citations = [
            CitationQM(
                index=idx,
                title="",
                source=f"www.a.com/{idx}",
                passage="",
                md_offset=text.find(str(idx)) - 1,
            )
            for idx in citation_indexes
        ]
        updated_text, updated_citations = (
            find_and_reorder_consecutive_citations(text, citations)
        )
        for previous_citation, citation in itertools.pairwise(
            updated_citations
        ):
            offset = citation.md_offset
            citation_md = citation.to_md()
            assert (
                updated_text[offset : offset + len(citation_md)] == citation_md
            )
            if citation.succeed(previous_citation):
                assert previous_citation.index < citation.index
            previous_citation = citation
