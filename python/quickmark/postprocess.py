import asyncio
from dataclasses import asdict
import logging
import functools
import html
import itertools
import mimetypes
import re
import textwrap
import urllib.parse
import xml.etree.ElementTree as etree
from collections import Counter, defaultdict, deque
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum, Flag, StrEnum, auto
from functools import lru_cache, wraps
from inspect import isgeneratorfunction
from string import Template
from typing import Annotated, Any, Literal, TypedDict

import numpy as np

from pydantic import BeforeValidator, BaseModel, Field, ConfigDict

import quickmark
from quickmark import MDParser, CitationQM, Plugin

logger = logging.getLogger("quickmark")


class AnswerBox(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str
    snippet: str = Field(alias="answer")
    url: str | None = Field(alias="link", default=None)
    time: str | None = None
    props: dict | None = None
    image: dict | None = None


class SearchResult(BaseModel):
    title: str | None
    url: str
    snippet: str | None = None
    rank: int = 0
    provider: str | None = None
    external_links: list[dict] | None = None
    text: str | None = None  # extracted text from result link
    source: str | None = None
    published_at: str | None = None
    time: str | None = None
    query: str = ""
    personal_rank: str | None = None
    props: dict | None = None
    image: dict | None = None

    def to_dict(self):
        return self.model_dump()

    @classmethod
    def from_node(cls, node):
        return cls(
            title=node.title,
            url=node.source,
            snippet=node.text,
            published_at=node.published_at,
            personal_rank=node.personal_rank,
            query=node.retrieval_query or "",
        )

    @classmethod
    def html_unescape_title(cls, title: str | None) -> str | None:
        """HTML unescape title."""
        if title is None:
            return None
        else:
            title = html.unescape(title)
            return title

    @classmethod
    def process_snippet(cls, snippet: str | None) -> str:
        """HTML unescape snippet and change None to empty string."""
        if snippet is None:
            return ""
        else:
            snippet = html.unescape(snippet)
            snippet = snippet.replace("<b>", "").replace("</b>", "")
            snippet = snippet.replace("<strong>", "").replace("</strong>", "")
            return snippet


class DocType(str, Enum):
    @staticmethod
    def _generate_next_value_(name, start, count, last_values) -> str:
        return name.lower()

    AUDIO = auto()
    TEXT = auto()
    JSON = auto()
    HTML = auto()
    PDF = auto()
    DOCX = auto()
    PPTX = auto()
    TABLE = auto()
    XLSX = auto()
    IMAGE = auto()
    EPUB = auto()
    ARXIV = auto()
    YOUTUBE = auto()
    TWITTER = auto()
    HACKERNEWS = auto()
    WEB = auto()
    DOCUMENT = auto()  # Generic document that we can't identify
    BOOK = auto()
    WIKIPEDIA = auto()
    QUORA = auto()
    RECIPES = auto()
    GITHUB = auto()
    REDDIT = auto()
    DISCOURSE = auto()
    WOLFRAM_SUMMARY_BOX = auto()
    SEARCH_RESULTS = auto()
    REFERENCES = auto()
    PUBMED = auto()
    WEB_SEARCH_ERROR = auto()
    # NOTE(Rehan): used to denote librarian response where there is no relevant content in the doc
    LIBRARIAN_NO_RELEVANT_CONTENT = auto()
    NO_CITE = auto()  # for nodes that we don't want cited
    BLUESKY = auto()
    BLOCKED_IP = auto()
    NYTIMES = auto()

    @property
    def plain_text(self) -> str:
        """Represent the member in plain text like prompt."""
        type_to_text = {
            "pdf": "PDF document",
            "pptx": "Powerpoint presentation",
            "audio": "Podcast audio",
            "youtube": "Youtube video",
            "twitter": "Twitter post",
            "hackernews": "Hacker News thread",
            "web": "Web page",
            "arxiv": "Research paper",
            "document": "Document",
            "image": "Image",
            "github": "GitHub Post",
            "reddit": "Reddit Post",
            "discourse": "Discourse Forum Post",
            "wolfram_summary_box": "Wolfram summary box",
            "search_results": "Search results",
            "pubmed": "PubMed article",
            "web_search_error": "Web search error",
        }
        return type_to_text.get(self.value, "Web page")

    @property
    def is_error(self) -> bool:
        """Check if type marks erroneous doc"""
        return self in [DocType.WEB_SEARCH_ERROR]


class Image(BaseModel):
    base64_image: str
    detail: Literal["low", "high", "auto"] = "auto"
    type: Literal["image"] = "image"


@dataclass
class ExtractedDocument:
    doc_type: DocType
    source: str = ""  # url or filename
    title: str = ""
    text: str | None = None
    base64_encoding: str | None = None
    length: int | None = None
    snippet: str | None = None
    extraction_latency: int = 0  # in ms
    extraction_cost: float = 0
    is_search_result: bool = False
    image_url: str | None = None
    extra_base64_encodings: list[str] | None = None
    authors: str | None = None

    # cast from str to enum during json deserialization
    def __post_init__(self):
        if not isinstance(self.doc_type, DocType):
            self.doc_type = DocType(self.doc_type)

    @classmethod
    def from_input_text(cls, text: str, title: str = ""):
        """Cast user input text to extracted doc."""
        if len(text) > 8_000_000 or len(text) < 50:
            raise ValueError(f"document size invalid : {len(text)}")

        return cls(
            doc_type=DocType.TEXT,
            source="user_uploaded_text.txt",
            title=title,
            text=text,
        )

    def to_dict(self):
        return asdict(self)

    # alias for source
    @property
    def url(self) -> str | None:
        if self.source.startswith("http"):
            return self.source
        else:
            return None

    @property
    def is_wolfram_result(self) -> bool:
        return self.source.startswith("https://www.wolframalpha.com")


@dataclass
class NodeChunk:
    """A node represents chunk of document or an image.
    Document can be extracted from web, API output, or uploaded document.
    """

    source: str  # url or filename
    title: str
    text: str  # chunk of text or snippet
    doc_type: DocType | None = None
    published_at: str | None = None
    personal_rank: str | None = None
    is_search_result: bool = False
    retrieval_query: str | None = None
    image_url: str | None = None
    image: Image | None = None
    parent: ExtractedDocument | None = None
    context: str | None = None

    # cast from str to enum during json deserialization
    def __post_init__(self):
        if self.doc_type is not None and not isinstance(self.doc_type, DocType):
            self.doc_type = DocType(self.doc_type)

    @classmethod
    def from_document(cls, document: ExtractedDocument):
        if document.base64_encoding:
            image = Image(base64_image=document.base64_encoding)
        else:
            image = None
        return cls(
            source=document.source,
            title=document.title,
            text=document.text or "",
            doc_type=document.doc_type,
            image=image,
            parent=document,
        )

    @classmethod
    def from_search_result(cls, search_result: SearchResult):
        return cls(
            doc_type=DocType.SEARCH_RESULTS,
            source=search_result.url,
            title=search_result.title or "",
            text=search_result.snippet or "",
            published_at=search_result.time or search_result.published_at or "",
            is_search_result=True,
            image_url=search_result.image.get("url")
            if search_result.image
            else None,
            retrieval_query=search_result.query,
            personal_rank=search_result.personal_rank,
        )

    @classmethod
    def from_answer_box(
        cls, answer_box: AnswerBox, search_query: str | None = None
    ):
        if not answer_box.url:
            raise ValueError(
                "Can't create document from answerbox without source"
            )
        return cls(
            doc_type=DocType.WEB,
            source=answer_box.url,
            title=answer_box.title,
            text=answer_box.snippet,
            is_search_result=True,
            retrieval_query=search_query,
        )

    @classmethod
    def from_wikipedia(
        cls, wikipedia: Wikipedia, search_query: str | None = None
    ):
        summary = wikipedia.summary or ""
        table = wikipedia.table or ""
        text = f"{summary}\n\n{table}".strip()

        return cls(
            doc_type=DocType.WIKIPEDIA,
            source=wikipedia.url,
            title=wikipedia.title,
            text=text,
            is_search_result=True,
            retrieval_query=search_query,
        )

    @classmethod
    def from_summary_box(
        cls, summary_box: SummaryBox, search_query: str | None = None
    ):
        return cls(
            doc_type=DocType.WOLFRAM_SUMMARY_BOX,
            source=summary_box.url,
            title=summary_box.title,
            text=summary_box.snippet,
            is_search_result=True,
            retrieval_query=search_query,
        )

    def to_dict(self):
        return asdict(self)

    @property
    def is_error(self) -> bool:
        return bool(self.doc_type and self.doc_type.is_error)

    @property
    def uncitable_image(self) -> bool:
        # NOTE(Rehan): idea here is if there is a node that is useful for just its image, deem it uncitable
        return (not self.text and self.image_url is not None) or (
            self.source == self.image_url
        )

    @property
    def uncitable(self) -> bool:
        return (
            self.uncitable_image
            or self.is_error
            or self.doc_type is DocType.NO_CITE
        )


class Reference(BaseModel):
    index: int = Field(exclude=True)
    title: str
    source: str = Field(serialization_alias="url")
    passages: list[str] = Field(exclude=True)
    citation_contribution: int = 0
    snippet: str | None = None
    full_text: str | None = Field(default=None, exclude=True)
    is_search_result: bool = Field(default=False)

    @property
    def is_url_source(self) -> bool:
        return self.source.startswith("http")

    def to_md(self) -> str:
        if self.is_url_source:
            return f"[{self.index}] [{self.title}]({self.source})"
        else:
            if self.title:
                return f"[{self.index}] {self.title} ({self.source})"
            else:
                return f"[{self.index}] {self.source}"

    @property
    def html_title(self) -> str:
        return html.escape(self.title)

    @property
    def html_source(self) -> str:
        return html.escape(self.source)

    def to_html(self, open_links_in_new_tab: bool):
        if self.is_url_source:
            target = 'target="_blank"' if open_links_in_new_tab else ""
            reference_template = Template(
                '<li><a href="$url" $target>$title</a> <span class="__domain-name">$domain</span></li>'
            )
            return reference_template.substitute(
                url=self.source,
                domain=urllib.parse.urlparse(self.source).hostname,
                title=self.html_title,
                target=target,
            )
        else:
            if self.title:
                reference_template = Template("<li>$title($source)</li>")
            else:
                reference_template = Template("<li>$source</li>")
            return reference_template.substitute(
                title=self.html_title, source=self.html_source
            )

    def to_bigquery_row(self):
        if "/settings/note_edit" in self.source:
            return {}

        parsed_url = urllib.parse.urlparse(self.source)
        if not (parsed_url.scheme and parsed_url.netloc):
            return {}
        host = parsed_url.netloc
        rest = self.source.split(parsed_url.netloc)[-1]

        return {
            "contribution_length": self.citation_contribution,
            "host": host,
            "path": rest,
        }


class PrecheckMode(Enum):
    ALL = "all"
    ANY = "any"


SINGLE_BACKTICK_PATTERN = re.compile(
    r"(?<![\\`])"  # no preceeding backslash or backtick
    r"`(?!`)"  # opening backtick, not followed by another
    r"(?P<code>(?:[^\\`]|\\.)+?)"  # code between valid single ticks
    r"`(?!`)"  # closing backtick, not followed by another
)
# citations in 1 square bracket that have spaces, comma, and dash in between
COMBINED_CITATIONS_PATTERN = re.compile(r"(【)(\s{0,3}\d+[,\-\d\s]*)(】)")

# - Full image tag with following chars, including surrounding newlines (group 0)
# - Full image tag with following chars (group 1)
# - Just full image tag (group 2)
# - Alt text section with exclamation point and brackets (group 3)
# - Alt text content (group 4)
# - Opening parenthesis (group 5)
# - Image URL (group 6)
# - Optional closing parenthesis (group 7)
# - Any trailing content, up to a pipe ('|') character (table row separator) or newline (group 8)
IMAGE_MD_PATTERN = re.compile(
    r"\n?(((\!\[([^\]]+)\])(\()([^)]*)(\))?)([^|\n]*))"
)

LINK_MD_PATTERN = re.compile(
    r"(?<!!)"  # look back not exclamation mark
    r"\n?"  # zero or one new line
    r"\["  # open square bracket
    r"(?P<link_text>.+?)"  # match one or more non-line terminating chars (lazy), group 1
    r"\]"  # close square bracket
    r"(?P<open_parenthesis>\()"  # open parenthesis, group 2
    r"(?P<url>[^)]*)"  # zero or more characters except close parenthesis, group 3
    r"(?P<close_parenthesis>\))?"  # zero or one closing parenthesis, group 4
    r"(\n?)"  # zero or one new line
)

# NOTE(Rehan): same as LINK_MD_PATTERN, but check for optional exclamation point as well
# also avoid matching surrounding newlines to avoid consuming them in extension processing
LINK_OR_IMAGE_MD_PATTERN = re.compile(
    r"(?P<exclamation_point>!?)"  # zero or one exclaimation point, group 1
    r"\["  # open square bracket
    r"(?P<link_text>!?\[[^\]]*\]\([^)]*\)|[^\]]+)"  # group 2: matches either image markdown OR non-] characters
    r"\]"  # close square bracket
    r"(?P<open_parenthesis>\()"  # open parenthesis, group 3
    r"(?P<url>[^)]*)"  # zero or more characters except close parenthesis, group 4
    r"(?P<close_parenthesis>\))?"  # zero or one closing parenthesis, group 5
)

# - Opening triple backticks
# - Any content that is not triple backticks
# - closing backticks (optional)
CODE_BLOCK = re.compile(r"```.*?```|```.*", re.MULTILINE | re.DOTALL)

ESCAPED_DOLLAR_PATTERN = re.compile(r"\\\$(?!\$)")

INLINE_MATH_DOLLAR_PATTERN = re.compile(
    r"(?<![^\*\(\s：])"  # negative lookbehind: preceded by whitespace, asterisk, open bracket, or full width colon
    r"\$"  # opening dollar sign
    r"(?P<sp>\s?)"  # optional whitespace after opening dollar
    r"(?!\$|\s)"  # negative lookahead: not followed by dollar sign or space
    r"(?P<math>[^$\\]*(?:\\.[^$\\]*)*)"  # math content: no unescaped dollar signs (captured group)
    r"(?<!\\|\s)"  # negative lookbehind: not preceded by escape or space
    r"(?P=sp)"  # optional whitespace before closing dollar
    r"\$"  # closing dollar sign
    r"(?a:(?!\$|\w))",  # negative lookahead with ASCII flag: not followed by dollar or word character
    re.ASCII,
)


# detect inline match delimited by '\(' and '\)'
# exclude \( and \) pairs escaped by backslash before the delimiters
INLINE_MATH_PAREN_PATTERN = re.compile(r"(?<!\\)\\\((?P<math>.*?)(?<!\\)\\\)")

# detect display latex wrapped in $$text$$, exclude escaped $ and inline latex $text$
DISPLAY_MATH_DOLLAR_PATTERN = re.compile(
    r"(?<!\\)\$\$(?:\n)?(?P<math>.*?)(?<!\\)(?:\n)?\$\$", re.DOTALL
)

# detect display latex wrapped in '\[' and '\]'
# Enable the ?s flag to allow . to match newline as display math can span multiple lines (e.g., align)
# exclude \[ and \] pairs escaped by backslash before the delimiters
DISPLAY_MATH_BRACKET_PATTERN = re.compile(
    r"(?<!\\)\\\[(?P<math>.*?)(?<!\\)\\\]", re.DOTALL
)

# - match \documentclass literally
# - optionally matches parameters in square brackets
# - match required argument in curly braces
DOCUMENT_CLASS_PATTERN = r"\\documentclass(?:\[.*\])?\{.*}"

# Currently only support North American phone number format
# - can only be at the start of the text or after an open parenthesis or space (avoid matching in URL)
# - optional country code with +, 1 to 3 digits
# - separator is a must, can be space, hyphen, or period
# - area code in parenthesis or not, 3 digits
# - 3-3-4 format, 10 digits in total
PHONE_NUMBER_PATTERN = re.compile(
    r"(?:(?<=^)|(?<=\()|(?<=\s))((\+?\d{1,3}[\s-]?)?(?:\(\d{3}\)|\d{3})[\s.-]\d{3}[\s.-]\d{4})"
)

# Check if preceded by start of line or whitespace and proceeded by non-word char (e.g punctuation) or end of line
# Do this instead of word boundary, because word boundary includes backslash, which may match within URL
EMAIL_PATTERN = re.compile(
    r"(?:\s|^)([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})(?:\W|$)"
)

# LaTeX env macros that should be filtered out in the output
UNWANTED_ENVIRONMENTS = [
    # Document structure
    "document",
    "abstract",
    "titlepage",
    # Front matter
    "title",
    "author",
    "date",
    "thanks",
    "address",
    "dedication",
    "acknowledgments",
    # Page layout
    "minipage",
    "multicols",
    "twocolumn",
    "landscape",
    "appendix",
    # Sectioning
    "chapter",
    "section",
    "subsection",
    "subsubsection",
    "paragraph",
    # Floating environments
    "figure",
    "table",
    "wrapfigure",
    # Bibliography/References
    "thebibliography",
    "bibliography",
    "references",
    # Other structural elements
    "frontmatter",
    "mainmatter",
    "backmatter",
    "tableofcontents",
    "listoffigures",
    "listoftables",
]
BEGIN_PATTERN = re.compile(
    r"\\begin\{(" + "|".join(UNWANTED_ENVIRONMENTS) + r")\}"
)
END_PATTERN = re.compile(r"\\end\{(" + "|".join(UNWANTED_ENVIRONMENTS) + r")\}")

COT_TAGS = ["think", "thinking"]

LIST_REGEX = r"^([*\-+]|[0-9]+[.])[ \t]+"  # match line starts with *, -, +, or digit follow by period, and indentation

URL_SUBSTRING_TO_BE_PROXIED = {
    "https://storage.googleapis.com/kagi",
    "https://bfldeliverysc.blob.core.windows.net/results",
}

GENERATED_CONTENT_APPENDIX = "*Generated content expires after 10 minutes.*"
SINGLE_BACKTICK_PLACEHOLDER = "【‡SINGLE_BACKTICK‡】"


def is_url_to_be_proxied(url: str) -> bool:
    return any(substring in url for substring in URL_SUBSTRING_TO_BE_PROXIED)


def remove_substring(text: str, start_index: int, end_index: int) -> str:
    return "".join([text[:start_index], text[end_index:]])


def insert_substring(text: str, insert_index: int, substring: str) -> str:
    return "".join([text[:insert_index], substring, text[insert_index:]])


def replace_substring(
    text: str, start_index: int, end_index: int, substring: str
) -> str:
    return "".join([text[:start_index], substring, text[end_index:]])


# Helper for decorator below
def empty_generator():
    for _ in range(0):
        yield


def regex_precheck(required_strings: str | tuple, mode: PrecheckMode):
    """Quickly check some whether text contain certain string before running expensive regex.
    if the precheck mode is ALL, the function call is skipped if text doesn't contain *all* required strings.
    if the precheck mode is ANY, the function call is skipped if text doesn't contain *any* required strings.
    For normal function, it return the text as is.
    For generator function, it yield nothing and return immediately.
    Wrapped function first argument must be a string.
    """
    if isinstance(required_strings, str):
        required_strings = (required_strings,)

    if mode not in PrecheckMode:
        raise ValueError(f"Invalid PrecheckMode: {mode}")

    def dec(fn):
        @wraps(fn)
        def wrapper(text: str, *args, **kwargs):
            if (
                mode is PrecheckMode.ANY
                and not any(s in text for s in required_strings)
            ) or (
                mode is PrecheckMode.ALL
                and not all(s in text for s in required_strings)
            ):
                return text
            else:
                return fn(text, *args, **kwargs)

        @wraps(fn)
        def generator_wrapper(text: str, *args, **kwargs):
            if (
                mode is PrecheckMode.ANY
                and not any(s in text for s in required_strings)
            ) or (
                mode is PrecheckMode.ALL
                and not all(s in text for s in required_strings)
            ):
                yield from empty_generator()
            else:
                yield from fn(text, *args, **kwargs)

        if isgeneratorfunction(fn):
            return generator_wrapper
        else:
            return wrapper

    return dec


# Code block functions
@regex_precheck("`", PrecheckMode.ALL)
def single_backtick_sub(text: str):
    return SINGLE_BACKTICK_PATTERN.sub(
        lambda matchobj: f"```{SINGLE_BACKTICK_PLACEHOLDER}{matchobj.group('code')}{SINGLE_BACKTICK_PLACEHOLDER}```",
        text,
    )


def replace_single_backtick(text: str) -> str:
    """Replace single backtick with triple backticks.
    They look the same in markdown and when convert to html.
    The exceptions are
    - characters inside are triple backticks (` ``` `)
    - the single backtick is inside triple backticks (``` ` ```)

    >>> replace_single_backtick("Some code here `[1,2,3]`").replace(SINGLE_BACKTICK_PLACEHOLDER, "")
    'Some code here ```[1,2,3]```'

    >>> replace_single_backtick("Triple backticks unchanged ```[1,2,3]```").replace(SINGLE_BACKTICK_PLACEHOLDER, "")
    'Triple backticks unchanged ```[1,2,3]```'

    >>> replace_single_backtick("No change if characters inside are triple backticks ` ``` `").replace(SINGLE_BACKTICK_PLACEHOLDER, "")
    'No change if characters inside are triple backticks ` ``` `'

    >>> replace_single_backtick("No change if single backtick is inside triple backticks ``` ` ```").replace(SINGLE_BACKTICK_PLACEHOLDER, "")
    'No change if single backtick is inside triple backticks ``` ` ```'

    >>> replace_single_backtick("No change if single backticks escaped \\\\`hello\\\\`").replace(SINGLE_BACKTICK_PLACEHOLDER, "")
    'No change if single backticks escaped \\\\`hello\\\\`'
    """
    text_split_by_codeblock = text.split("```")
    non_code_texts = text_split_by_codeblock[::2]
    processed_text = map(single_backtick_sub, non_code_texts)
    text_split_by_codeblock[::2] = processed_text
    return "```".join(text_split_by_codeblock)


def restore_single_backtick(text: str) -> str:
    """Undo replace_single_backtick function

    >>> restore_single_backtick(replace_single_backtick("This is an `inline` code."))
    'This is an `inline` code.'
    """
    return text.replace(f"```{SINGLE_BACKTICK_PLACEHOLDER}", "`").replace(
        f"{SINGLE_BACKTICK_PLACEHOLDER}```", "`"
    )


def protect_codeblock(
    include_inline_code: bool = True, code_placeholder: bool = False
):
    """Apply function to text outside codeblock only.
    Text to be processed should be first positional arg of function.
    """

    def dec(fn):
        @wraps(fn)
        def wrapper(text, *args, **kwargs):
            if include_inline_code:
                text = replace_single_backtick(text)
            codeblock_separator = "```"
            text_split_by_codeblock = text.split(codeblock_separator)
            non_code_texts = text_split_by_codeblock[::2]
            if code_placeholder:
                processed_text = fn(
                    "```【‡code_placeholder‡】```".join(non_code_texts),
                    *args,
                    **kwargs,
                )
                processed_text = processed_text.split(
                    "```【‡code_placeholder‡】```"
                )
            else:
                processed_text = (
                    fn(passage, *args, **kwargs) for passage in non_code_texts
                )
            text_split_by_codeblock[::2] = processed_text
            output_text = codeblock_separator.join(text_split_by_codeblock)
            if include_inline_code:
                output_text = restore_single_backtick(output_text)
            return output_text

        return wrapper

    return dec


@regex_precheck(("【", "】"), PrecheckMode.ALL)
def split_citations(answer: str) -> str:
    r"""
    Split multiple references in a square bracket into multiple square brackets.
    Examples:
    >>> split_citations("This is an multiple-sources references 【3,7,8】")
    'This is an multiple-sources references 【3】【7】【8】'

    >>> split_citations("This is another multiple-sources references 【1-4】")
    'This is another multiple-sources references 【1】【2】【3】【4】'

    >>> split_citations("This is an answer with a mix of comma and dash 【1,3-5】")
    'This is an answer with a mix of comma and dash 【1】【3】【4】【5】'

    >>> split_citations("This is an answer with original format 【1】【3】")
    'This is an answer with original format 【1】【3】'

    >>> split_citations("This is how you build a list ```l = [1,2,3]```.")
    'This is how you build a list ```l = [1,2,3]```.'

    >>> split_citations("This is how you build a list `l = [1,2,3]`.")
    'This is how you build a list `l = [1,2,3]`.'

    >>> split_citations("This is how you include math \\[ \\text{proj}_{\\vec{v}} \\vec{u} = \\frac{2}{3} [9, -3] = [6, -2] \\].")
    'This is how you include math \\[ \\text{proj}_{\\vec{v}} \\vec{u} = \\frac{2}{3} [9, -3] = [6, -2] \\].'

    >>> split_citations("This is how you include math \\( \\text{proj}_{\\vec{v}} \\vec{u} = \\frac{2}{3} [9, -3] = [6, -2] \\).")
    'This is how you include math \\( \\text{proj}_{\\vec{v}} \\vec{u} = \\frac{2}{3} [9, -3] = [6, -2] \\).'

    >>> split_citations("This is how you include math $ \\text{proj}_{\\vec{v}} \\vec{u} = \\frac{2}{3} [9, -3] = [6, -2] $.")
    'This is how you include math $ \\text{proj}_{\\vec{v}} \\vec{u} = \\frac{2}{3} [9, -3] = [6, -2] $.'

    >>> split_citations("This is how you include math $$ \\text{proj}_{\\vec{v}} \\vec{u} = \\frac{2}{3} [9, -3] = [6, -2] $$.")
    'This is how you include math $$ \\text{proj}_{\\vec{v}} \\vec{u} = \\frac{2}{3} [9, -3] = [6, -2] $$.'

    >>> split_citations("Here is a list of integers in plain text: [-1, 2, 3].")
    'Here is a list of integers in plain text: [-1, 2, 3].'
    """

    def expand_references(ref_str: str) -> list:
        refs = []
        for ref in ref_str.split(","):
            if "-" in ref:
                # Expand range of references
                start, end = map(int, ref.split("-"))
                refs.extend(range(start, end + 1))
            else:
                # Single reference
                refs.append(int(ref))
        return refs

    processed_answer = re.sub(
        COMBINED_CITATIONS_PATTERN,
        lambda m: "".join(f"【{i}】" for i in expand_references(m.group(2))),
        answer,
    )
    return processed_answer


@regex_precheck(("【", "】"), PrecheckMode.ANY)
def remove_citation_bold(answer: str) -> str:
    """Remove bold markdown for citations

    >>> remove_citation_bold("This citation has bold 【**1**】.")
    'This citation has bold 【1】.'

    >>> remove_citation_bold("Correct citation format 【1】.")
    'Correct citation format 【1】.'

    >>> remove_citation_bold("Text without citation.")
    'Text without citation.'
    """
    answer = re.sub(
        r"【\*\*(\d+)\*\*】",
        lambda matchobj: f"【{matchobj.group(1)}】",
        answer,
    )
    return answer


@regex_precheck(("【", "】"), PrecheckMode.ANY)
def standardize_citation_bracket(answer: str) -> str:
    """
    >>> standardize_citation_bracket('Sample citation with valid syntax【1】.')
    'Sample citation with valid syntax【1】.'
    """
    return re.sub(
        r"【(\d+)】", lambda matchobj: f"【{matchobj.group(1)}】", answer
    )


@regex_precheck(("【", "】"), PrecheckMode.ALL)
def remove_invalid_citations(answer: str) -> str:
    """Remove invalid citations that contain letters

    >>> remove_invalid_citations("This citation has letters 【undefined】.")
    'This citation has letters.'

    >>> remove_invalid_citations("This citation has letters 【not cited, as this info is not available in the provided passages】.")
    'This citation has letters.'

    >>> remove_invalid_citations("Valid citation 【1】.")
    'Valid citation 【1】.'

    >>> remove_invalid_citations("Valid citations 【1】【2】.")
    'Valid citations 【1】【2】.'

    >>> remove_invalid_citations("Text without citation.")
    'Text without citation.'

    >>> remove_invalid_citations("【abc】【123】【def】")
    '【123】'
    """
    open_bracket = "【"
    close_bracket = "】"
    last_end_pos = 0
    while True:
        start_pos = answer.find(open_bracket, last_end_pos)
        end_pos = answer.find(close_bracket, start_pos)
        if start_pos != -1 and end_pos != -1:
            substring_in_bracket = answer[start_pos + 1 : end_pos]
            if not substring_in_bracket.isdigit():
                if start_pos >= 1 and answer[start_pos - 1].isspace():
                    start_pos -= 1
                if end_pos + 1 < len(answer) and answer[end_pos + 1].isspace():
                    end_pos += 1
                answer = remove_substring(answer, start_pos, end_pos + 1)
            last_end_pos = end_pos
        else:
            break

    return answer


@regex_precheck(("【", "】"), PrecheckMode.ALL)
def detect_citation(answer: str) -> Generator[re.Match, None, None]:
    """Yield citation in non-code text"""
    for match_obj in re.finditer(r"【(\d+)】", answer):
        yield match_obj


def extract_citations(
    answer: str,
    passages: list[NodeChunk],
    truncate_citations: bool = True,
) -> tuple[str, list[CitationQM], bool]:
    """Remove citation from text and store in a list of citations"""
    counter = itertools.count(1)
    source_to_reenumerated_index = defaultdict(lambda: next(counter))

    # offset for string we have removed
    rolling_offset = 0
    prev_citation_char_end = -1
    running_cited_sources = set()

    citations = []
    citation_truncated = False

    for citation_match in detect_citation(answer):
        cited_index = int(citation_match.group(1))
        citation_start_char, citation_end_char = citation_match.span()

        # skip invalid indexess
        if cited_index not in range(1, len(passages) + 1):
            answer = remove_substring(
                answer,
                citation_start_char - rolling_offset,
                citation_end_char - rolling_offset,
            )
            rolling_offset += citation_end_char - citation_start_char
            prev_citation_char_end = citation_end_char
            continue

        cited_passage = passages[cited_index - 1]
        cited_source = cited_passage.source

        # NOTE(boon): remove citations from same source but different snippets.
        # eg: here is a claim[1][2][1]
        # will remove this after we support sub-citations like 1a, 1b
        if prev_citation_char_end == citation_start_char:
            if cited_source in running_cited_sources or (
                truncate_citations
                and (citation_truncated := len(running_cited_sources) == 2)
            ):
                answer = remove_substring(
                    answer,
                    citation_start_char - rolling_offset,
                    citation_end_char - rolling_offset,
                )
                rolling_offset += citation_end_char - citation_start_char
                prev_citation_char_end = citation_end_char
                continue

            running_cited_sources.add(cited_source)
        else:
            running_cited_sources.clear()
            running_cited_sources.add(cited_source)

        prev_citation_char_end = citation_end_char
        updated_index = source_to_reenumerated_index[cited_source]

        md_offset = citation_start_char - rolling_offset

        full_text_cited = False
        cited_doc = cited_passage.parent
        if isinstance(cited_doc, ExtractedDocument) and (
            cited_passage.text == cited_doc.text
        ):
            full_text_cited = True

        citation = CitationQM(
            index=updated_index,
            title=cited_passage.title,
            source=cited_source,
            passage="Full document cited. View source for more information."
            if full_text_cited
            else cited_passage.text,
            md_offset=md_offset,
        )
        updated_index_text = citation.to_md()

        answer = replace_substring(
            answer,
            md_offset,
            citation_end_char - rolling_offset,
            updated_index_text,
        )

        citations.append(citation)
        rolling_offset += len(citation_match.group()) - len(updated_index_text)

    return answer, citations, citation_truncated


def get_excerpt_and_citation(
    text: str, citations: list[CitationQM]
) -> dict[str, list[CitationQM]]:
    """Return excerpt to citations mapping."""
    last_citation = None
    last_citation_end = 0
    last_excerpt = ""
    excerpt_bucket: dict[str, list[CitationQM]] = defaultdict(list)

    # TODO: Don't needlessly sort?
    citations = sorted(citations, key=lambda x: x.md_offset)

    for citation in citations:
        if last_citation is not None and citation.succeed(last_citation):
            excerpt = last_excerpt
        else:
            excerpt = (
                text[last_citation_end : citation.md_offset]
                .rstrip("\n")
                .rsplit("\n")[-1]
                .removeprefix(". ")
            )
        if len(excerpt):
            excerpt_bucket[excerpt].append(citation)
        else:
            logger.error(f"Excerpt length is zero: {text}")
        last_citation = citation
        last_citation_end = citation.md_offset + len(citation.to_md())
        last_excerpt = excerpt
    return excerpt_bucket


def calculate_reference_contribution(
    text: str,
    citations: list[CitationQM],
    excerpt_bucket: dict[str, list[CitationQM]],
) -> tuple[np.ndarray, list[int]]:
    total_excerpt_length = sum(len(excerpt) for excerpt in excerpt_bucket)
    if total_excerpt_length == 0:
        raise ValueError(f"Zero attributable excerpt {text} {citations}")
    passage_counter = Counter(citation.passage for citation in citations)
    citation_contribution = np.zeros(
        max(citation.index for citation in citations)
    )
    # Return immediately if there is only one source
    if citation_contribution.size == 1:
        return np.array([100], dtype=int), [
            sum(len(excerpt) for excerpt in excerpt_bucket)
        ]

    for excerpt, citations_list in excerpt_bucket.items():
        # If excerpt has only one source, skip calculation
        if len(citations_list) == 1:
            citation_contribution[citations_list[0].index - 1] += len(excerpt)
            continue

        effective_length = sum(
            citation.passage_length / passage_counter[citation.passage]
            for citation in citations_list
        )
        for citation in citations_list:
            divider = effective_length * passage_counter[citation.passage]
            if divider == 0:
                continue

            weight = citation.passage_length / divider
            citation_contribution[citation.index - 1] += max(
                0, len(excerpt) * weight
            )

    total_contribution = citation_contribution.sum()
    if total_contribution == 0:
        raise ValueError(f"Zero total contribution {text} {citations}")

    percentages = (citation_contribution / total_contribution) * 100
    if np.any((percentages < 0) | (percentages > 100)):
        raise ValueError(
            f"An unexpected percentage value observed {text}\n{citations}\n{str(percentages)}"
        )

    citation_contribution = citation_contribution.astype(int).tolist()
    percentages_int = np.round(percentages).astype(int)
    diff = 100 - percentages_int.sum()
    if diff != 0:
        fractional_parts = percentages - percentages_int
        indices = np.argsort(fractional_parts)
        adjusted_value = -1
        if diff > 0:
            indices = indices[::-1]
            adjusted_value = 1

        indices_to_be_adjusted = indices[: np.abs(diff)]
        percentages_int[indices_to_be_adjusted] += adjusted_value

    return percentages_int, citation_contribution


def reorder_consecutive_citations(
    text: str, citations: list[CitationQM], group: list[tuple[int, int]]
) -> tuple[str, list[CitationQM]]:
    if len(group) < 2:
        return text, citations

    ordered_citations = sorted(citations, key=lambda citation: citation.index)
    offset = 0
    for idx, span in enumerate(group):
        text_offset = span[0] + offset
        old_index = str(citations[idx].index)
        new_index = str(ordered_citations[idx].index)
        text = text[:text_offset] + text[text_offset:].replace(
            old_index, new_index, 1
        )
        offset += len(new_index) - len(old_index)
        ordered_citations[idx] = ordered_citations[idx].model_copy(
            update={"md_offset": text_offset}
        )
    return text, ordered_citations


def find_and_reorder_consecutive_citations(
    text: str, citations: list[CitationQM]
) -> tuple[str, list[CitationQM]]:
    if len(citations) < 2:
        return text, citations

    matches = list(detect_citation(text))
    group_start = 0
    group = [matches[0].span()]
    for idx, (prev_match, current_match) in enumerate(
        itertools.pairwise(matches), start=1
    ):
        if current_match.start() != prev_match.end():
            text, citations[group_start:idx] = reorder_consecutive_citations(
                text, citations[group_start:idx], group
            )
            group.clear()
            group_start = idx

        group.append(current_match.span())
    if group:
        text, citations[group_start:] = reorder_consecutive_citations(
            text, citations[group_start:], group
        )

    return text, citations


def reorder_references_by_contribution(
    text: str,
    citations: list[CitationQM],
    percentages: np.ndarray,
    citation_contribution: list[int],
) -> tuple[str, list[CitationQM]]:
    # chr(0x41) -> A
    placeholders = {
        citation.index: f"【{chr(0x41 + citation.index)}】)"
        for citation in citations
    }
    for idx, placeholder in placeholders.items():
        text = text.replace(f"【{idx}】", placeholder)

    argsorted = np.argsort(np.argsort(-percentages)).tolist()
    percentages = percentages.tolist()

    new_citations = []
    md_offset_shift = 0
    for citation in citations:
        new_idx = argsorted[citation.index - 1] + 1
        new_citations.append(
            citation.model_copy(
                update={
                    "index": new_idx,
                    "percentage": percentages[citation.index - 1],
                    "md_offset": citation.md_offset + md_offset_shift,
                    "citation_contribution": citation_contribution[
                        citation.index - 1
                    ],
                }
            )
        )
        md_offset_shift += len(str(new_idx)) - len(str(citation.index))
        text = text.replace(placeholders[citation.index], f"【{new_idx}】")
    return text, new_citations


def reference_contribution(
    text: str, citations: list[CitationQM]
) -> tuple[str, list[CitationQM]]:
    if len(citations) == 0:
        return text, citations

    excerpt_bucket = get_excerpt_and_citation(text, citations)
    percentages, citation_contribution = calculate_reference_contribution(
        text, citations, excerpt_bucket
    )
    text, citations = reorder_references_by_contribution(
        text, citations, percentages, citation_contribution
    )
    text, citations = find_and_reorder_consecutive_citations(text, citations)
    return text, citations


def postprocess_citation(
    text: str, passages: list[NodeChunk], truncate_citations: bool = True
) -> tuple[str, list[CitationQM], bool]:
    text = split_citations(text)
    text = remove_citation_bold(text)
    text = standardize_citation_bracket(text)
    text = remove_invalid_citations(text)
    citable_nodes = [node for node in passages if not node.uncitable]
    text, citations, citation_truncated = extract_citations(
        text, citable_nodes, truncate_citations
    )
    return text, citations, citation_truncated


def convert_citations_to_references(
    citations: list[CitationQM],
    extracted_documents: list[NodeChunk],
) -> list[Reference]:
    sorted_citations = sorted(citations, key=lambda x: x.index)
    # the source of an extracted document can be either url (web search result) or file name (user uploaded file)
    source_to_document = {
        document.source: document for document in extracted_documents
    }

    references = []
    for (index, source), grouped_citations in itertools.groupby(
        sorted_citations, key=lambda x: (x.index, x.source)
    ):
        cited_result = source_to_document.get(source)
        if cited_result is None:
            continue

        passages = []
        citation_contribution = 0
        for citation in grouped_citations:
            passages.append(citation.passage)
            citation_contribution = citation.citation_contribution

        reference = Reference(
            index=index,
            title=cited_result.title,
            source=source,
            passages=passages,
            citation_contribution=citation_contribution,
            snippet=cited_result.text,
            full_text=cited_result.text,
            is_search_result=cited_result.is_search_result,
        )
        references.append(reference)
    return references


def make_references(references: list[Reference]) -> str:
    """
    >>> make_references([])
    ''

    >>> make_references([Reference(index=1, title="t1", source="http://link1", passages=[])])
    '[1] [t1](http://link1)'

    >>> make_references([Reference(index=1, title="t1", source="test.txt", passages=[])])
    '[1] t1 (test.txt)'

    >>> make_references([Reference(index=1, title="", source="test.txt", passages=[])])
    '[1] test.txt'
    """
    return "  \n".join(reference.to_md() for reference in references)


def format_references(
    references: list[Reference], open_links_in_new_tab: bool
) -> str:
    """
    HTML format references to an ordered list

    >>> format_references([], True)
    ''
    """
    if not references:
        return ""
    reference_div = '<div class="_0_quick_answer_links"><ol>'
    reference_close_div = "</ol></div>"
    references_body = "\n".join(
        reference.to_html(open_links_in_new_tab=open_links_in_new_tab)
        for reference in references
    )
    return f"{reference_div}{references_body}{reference_close_div}"


def complete_backtick(text: str) -> str:
    """Complete the string with unclosed backtick.
    This is mainly for streaming text for 2 reasons.

    - The streaming text will convert to html properly, so code comment don't become heading tag.
    - Avoid malicious code rendering in "<code>malicious code" format. Adding closing backtick will add
    the closing code tag in html.

    Only completes code blocks where the opening ``` is at the beginning of a line (with optional leading whitespace).
    This prevents completing inline mentions like 'I need to use ```html to ...'

    >>> complete_backtick("This is a text without code.")
    'This is a text without code.'

    >>> complete_backtick("This is a text with complete code\\n ```1 + 1\\n```.")
    'This is a text with complete code\\n ```1 + 1\\n```.'

    >>> complete_backtick("Line break before\\n```incomplete code")
    'Line break before\\n```incomplete code\\n```'

    >>> complete_backtick("Partially complete\\n```1+1\\n`")
    'Partially complete\\n```1+1\\n```'

    >>> complete_backtick("I need to use ```html to format this.")
    'I need to use ```html to format this.'

    >>> complete_backtick("At start of text ```code\\nmore")
    'At start of text ```code\\nmore'

    >>> complete_backtick("Line break before\\n```code\\nmore")
    'Line break before\\n```code\\nmore\\n```'

    >>> complete_backtick("With leading spaces\\n  ```code\\nmore")
    'With leading spaces\\n  ```code\\nmore\\n```'

    >>> complete_backtick("<details><summary>This is some code:\\n```\\ncode code code\\n</details>")
    '<details><summary>This is some code:\\n```\\ncode code code\\n```\\n</details>'

    >>> complete_backtick("hey\\n```test hey this test```\\nhii")
    'hey\\n```test hey this test```\\nhii'
    """
    has_thinking = (
        text.startswith("<details><summary>") and "</details>" in text
    )
    close_tag = None
    if has_thinking:
        thinking, close_tag, response = text.partition("</details>")
        splitted = [thinking, response]
    else:
        splitted = [text]

    processed = []
    for part in splitted:
        lines = part.split("\n")
        backtick_count = sum(
            line.count("```") == 1
            for line in lines
            if line.lstrip().startswith("```")
        )

        if backtick_count % 2 == 1:
            part = part.rstrip("\n`")
            part = f"{part}\n```"
        processed.append(part)

    # TODO(Rehan): Needs the newline before close or else if the close tag is on the same line
    # as the closing codeblock fence it can bug out. Not sure why though, feel like its something
    # with quickmark
    #
    # https://linear.app/kagi/issue/AI-2671/code-blocks-messing-with-librarian-dropdowns
    if has_thinking and close_tag:
        processed[0] = f"{processed[0]}\n{close_tag}"

    return "".join(processed)


# Rendering functions that involve HTML and markdown #
@protect_codeblock(include_inline_code=False)
def nest_list_with_4_spaces(text: str) -> str:
    """
    make sure nested list are indented with 4 spaces
    https://github.com/Python-Markdown/markdown/issues/1378
    """

    # NOTE(Rehan): Here we check what is used for the indentation level (e.g 2 vs 4 space)
    # This is checked by looking at the first list line that is indented
    # and using that as a reference for what is considered a single level indent
    # if it is less than 4 spaces, we expand all points to use 4 for each level of indentation.
    # If it is not using less than 4, we leave it.
    new_lines = []
    spaces_for_indent = 0
    for line in text.split("\n"):
        if not line:
            new_lines.append(line)
            continue

        # Convert only leading tabs to 4 spaces each
        num_leading_tabs = len(line) - len(line.lstrip("\t"))
        if num_leading_tabs > 0:
            line = (
                line[:num_leading_tabs].expandtabs(4) + line[num_leading_tabs:]
            )

        if is_list_line(line):
            line_dedented = line.lstrip()
            line_indent_spaces_used = len(line) - len(line_dedented)

            if line_indent_spaces_used == 0:
                new_lines.append(line)
                continue

            spaces_for_indent = spaces_for_indent or line_indent_spaces_used
            if spaces_for_indent < 4:
                indent_level = line_indent_spaces_used // spaces_for_indent
                new_indentation = indent_level * (" " * 4)
                line = f"{new_indentation}{line.lstrip()}"
        else:
            spaces_for_indent = 0
        new_lines.append(line)
    return "\n".join(new_lines)


def is_list_line(text_line: str) -> bool:
    r"""
    Returns True if a line is a markdown list line, False otherwise

    >>> is_list_line("Not a list line")
    False
    >>> is_list_line("- list item")
    True
    >>> is_list_line("* list item")
    True
    >>> is_list_line("15. list item")
    True
    >>> is_list_line("34.\tlist item")
    True
    >>> is_list_line("72.75 > 2\\sqrt{1320}")
    False
    >>> is_list_line("3.14159 is pi")
    False
    """
    stripped = text_line.lstrip()
    # Check for unordered list markers
    if stripped.startswith(("* ", "- ")):
        return True
    # Check for numbered list: digits followed by ". " (period + space)
    parts = stripped.split(".", 1)
    return (
        len(parts) == 2
        and parts[0].isdigit()
        and parts[1].startswith((" ", "\t"))
    )


def md_list_generator(text: str) -> Generator[str, None, None]:
    """Yield ordered and unordered list within text"""
    # Group consecutive lines by whether they're list lines
    for is_list, group in itertools.groupby(
        text.splitlines(), key=is_list_line
    ):
        if is_list:
            yield "\n".join(group)


@protect_codeblock(include_inline_code=False, code_placeholder=True)
def fix_list_spacing_indentation(text: str) -> str:
    """
    dedent markdown list and place newline between list and non list sections
    """
    for md_list in md_list_generator(text):
        dedented_list = textwrap.dedent(md_list)
        *texts_before_list, texts_after_list = text.split(md_list)
        stripped = [
            *[section.rstrip() for section in texts_before_list],
            texts_after_list,
        ]
        text = f"\n\n{dedented_list}".join(stripped)
    return text


def split_closing_code_block_and_citation(
    text: str,
) -> Generator[str, None, None]:
    for line in text.split("\n"):
        if (
            line.lstrip().startswith("```")
            and (citation_char_index := line.find("【")) != -1
        ):
            yield line[:citation_char_index].strip()
            yield line[citation_char_index:]
        else:
            yield line


def fix_code_block_with_citation(text: str) -> str:
    """
    If a citation is on the same line as the end of a code block, formatting gets messed up
    This moves the citation to the next line
    """
    if not ("\n```" in text and "【" in text):
        return text
    else:
        return "\n".join(split_closing_code_block_and_citation(text))


def replace_prime_notation(md_input):
    """from https://github.com/polarwinkel/mdtex2html/issues/2"""

    def replace_with_power(match):
        character = match.group(1)
        primes = match.group(2)
        power = len(primes)  # Count of prime symbols
        return f"{character}^{{({power})}}"

    # Corrected regular expression to match a character followed by three or more prime symbols (')
    pattern = r"(\w)('{3,})"

    md_input = re.sub(pattern, replace_with_power, md_input)

    return md_input


@protect_codeblock(include_inline_code=True)
def escape_html(text: str) -> str:
    """
    HTML escapes markdown text to prepare for HTML display or HTML parsing
    Will escape everything but code blocks.

    >>> escape_html("This is a <b> tag.")
    'This is a &lt;b&gt; tag.'
    >>> escape_html("This is a <b> tag. ```<b>This is a code block.</b>```")
    'This is a &lt;b&gt; tag. ```<b>This is a code block.</b>```'
    >>> escape_html("`<b>This is a code block.</b>`")
    '`<b>This is a code block.</b>`'
    """
    # NOTE(Ugur): Unescape before escape to neutralize any escaped character before preprocessing
    return html.escape(html.unescape(text))


ESCAPED_BR_TAGS = {html.escape(tag): tag for tag in ("<br>", "<br/>", "<br />")}


@protect_codeblock(include_inline_code=True, code_placeholder=True)
def unescape_br_in_table(text: str) -> str:
    """
    HTML unescapes <br> tags (and other variations of <br> tags) in tables
    """
    # NOTE(Rehan): Ki (4o) may use <br/> for line breaks in a table for some reason
    # https://linear.app/kagi/issue/SAM-4036/br-not-parsed-in-assistant-table
    # we determine what lines are table lines if they contain a pipe (|).
    # This can result in false positives, though these cases should be rare, low impact, and I'm not sure of a better way.
    contains_table = "-" in text and "|" in text
    if not contains_table:
        return text

    new_text = []
    for line in text.split("\n"):
        if "|" in line:
            for escaped, unescaped in ESCAPED_BR_TAGS.items():
                line = line.replace(escaped, unescaped)
        new_text.append(line)
    return "\n".join(new_text)


@protect_codeblock(include_inline_code=True)
def string_replace_codeblock_protected(text: str, old: str, new: str):
    return text.replace(old, new)


def get_tag_placeholder(tag: str):
    # NOTE(Rehan): stripping out <> here to make it less tag-like - possible it is still treated as a tag
    return f"‡‡{tag.strip('<>')}_PLACEHOLDER‡‡"


@protect_codeblock(include_inline_code=True)
def place_placeholders(
    text: str, tags: list[str], placeholders: list[str]
) -> str:
    for tag, placeholder in zip(tags, placeholders):
        text = text.replace(tag, placeholder)
    return text


@dataclass
class TextContainer:
    text: str


@contextmanager
def protect_tags(text: str, tags: list[str]):
    """
    context manager that replaces an HTML tag with a non tag placeholder, and reverses the replacement (and strips out any <p> tags surrounding placeholders) on exiting

    We can use this when we want to surround some text with HTML tags, but also want the contents to be converted to HTML.

    The alternatives are:
    - simply escape tags
        - markdown to html conversion will count this as HTML and will not touch at all, leaving contents unconverted
    - unescape tags after conversion
        - no clean way to avoid unescaping these tags in codeblocks

    Usage:
    text = <tag>hello</tag>
    with protect_tags(text, summary_tags) as container:
        # container.text has placeholders instead of <tag></tag>
        container.text = markdown.markdown(container.text, extensions=[])

    # placeholders are now reverted
    return container.text
    """
    container = TextContainer(text)
    placeholders = [get_tag_placeholder(tag) for tag in tags]
    container.text = place_placeholders(text, tags, placeholders)
    try:
        yield container
    finally:
        for tag, placeholder in zip(tags, placeholders):
            # NOTE(Rehan): here we can use regex, but since there are just four different strings we want to match lets just avoid it
            container.text = (
                container.text.replace(f"<p>{placeholder}</p>", tag)
                .replace(f"<p>{placeholder}", tag)
                .replace(f"{placeholder}</p>", tag)
                .replace(placeholder, tag)
            )


@protect_codeblock(include_inline_code=True)
def unescape_tags(text: str, tags: list[str]) -> str:
    """
    unescape XML tag in entire response, besides code (using protect_codeblock decorator)
    """
    for tag in tags:
        text = text.replace(html.escape(tag), tag)
    return text


def remove_wrapper_tag(text: str, tag_name: str) -> str:
    """
    Remove XML-style wrapper tag if it wraps the entire response.
    Strips newlines and whitespace before and after the tags.

    >>> remove_wrapper_tag("<result>actual response</result>", "result")
    'actual response'

    >>> remove_wrapper_tag("\\n<output>\\nactual response\\n</output>\\n", "output")
    'actual response'

    >>> remove_wrapper_tag("<result>actual response</result>", "output")
    '<result>actual response</result>'

    >>> remove_wrapper_tag("normal <result>text</result> with tags", "result")
    'normal <result>text</result> with tags'

    >>> remove_wrapper_tag("Just normal text", "result")
    'Just normal text'
    """
    open_tag = f"<{tag_name}>"
    close_tag = f"</{tag_name}>"

    return text.strip().removeprefix(open_tag).removesuffix(close_tag).strip()


def markdown_to_html_preprocess(text: str) -> str:
    text = nest_list_with_4_spaces(text)
    # remove trailing - with zero or more spaces
    # see test_unordered_list_become_heading
    text = re.sub(r"- *$", "", text)
    text = text.removesuffix("- ")
    text = fix_list_spacing_indentation(text)
    text = complete_backtick(text)
    text = escape_html(text)
    text = fix_code_block_with_citation(text)
    text = normalize_codeblocks(text)
    text = unescape_br_in_table(text)
    return text


@regex_precheck(("![", "]("), PrecheckMode.ALL)
def parse_image_link(text: str) -> Generator[tuple[str, str, str], None, None]:
    """Yield full_match, image_name, and image_url for all markdown images links in text"""
    # regex match 4 objects,
    # zero or one new line
    # image name in ![], only text inside is matched
    # url in () after image name matched, only text inside is matched
    # zero or one new line
    for match_obj in IMAGE_MD_PATTERN.finditer(text):
        full_match, image_name, image_url = match_obj.group(0, 4, 6)
        yield full_match, image_name, image_url


@protect_codeblock(include_inline_code=True)
def remove_images(text: str) -> str:
    """Remove image link in markdown text
    >>> remove_images("Non-exist image. \\n\\n![image9](image_url9)")
    'Non-exist image. \\n'

    >>> remove_images("Text without image.")
    'Text without image.'
    """
    for full_match, *_ in parse_image_link(text):
        text = text.replace(full_match, "")
    return text


@protect_codeblock(include_inline_code=True)
@regex_precheck(("![", "]"), PrecheckMode.ALL)
def process_images(text: str, image_urls: dict[str, str] | None = None) -> str:
    """
    Process generated images mid and post stream.
    - remove streaming images.
    - remove trailing content such as citation and period.
    - add caption about image expiring.

    >>> process_images("Text without image.")
    'Text without image.'

    >>> process_images("Incomplete image. \\n\\n![image9](image_", {"image": "image_link"})
    'Incomplete image. \\n'

    >>> process_images("Image. \\n\\n![image9](https://delivery-eu1.bfl.ai/results/xxxxx) 【0】 .\\n\\nNew paragraph.", {"image9" : "https://delivery-eu1.bfl.ai/results/xxxxx"})
    'Image. \\n\\n![image9](https://delivery-eu1.bfl.ai/results/xxxxx)\\n\\nNew paragraph.\\n\\n*Generated content expires after 10 minutes.*'

    >>> process_images("![Generated Image](https://delivery-eu1.bfl.ai/results/xxxxx)", {"Generated Image": "https://delivery-eu1.bfl.ai/results/xxxxx"})
    '![Generated Image](https://delivery-eu1.bfl.ai/results/xxxxx)\\n\\n*Generated content expires after 10 minutes.*'

    >>> process_images("![non generated image](search result image url)", {"non generated image" : "search result image url"})
    '![non generated image](search result image url)'

    >>> process_images("![a_generated_image](correct_url)", {"a_generated_image" : "incorrect_url"})
    '![a_generated_image](incorrect_url)'

    >>> process_images("![non generated image](search result image url)", {})
    ''
    """
    image_urls = image_urls or {}
    all_image_urls = image_urls.values()
    processed_image_urls = []

    generated_content_present = False

    for match_obj in IMAGE_MD_PATTERN.finditer(text):
        (
            full_match,
            title_text,
            image_url,
            closing_link_bracket,
            trailing_content,
        ) = match_obj.group(0, 4, 6, 7, 8)
        if image_url in processed_image_urls:
            continue

        updated_text = ""
        if closing_link_bracket and image_url in all_image_urls:
            updated_text = full_match.removesuffix(trailing_content)
            image_netloc = urllib.parse.urlparse(image_url).netloc
            if not generated_content_present:
                generated_content_present = any(
                    text in image_netloc
                    for text in [
                        "bfl.ai",
                        "oaidalleapiprodscus",
                        "storage.googleapis",
                    ]
                )
            processed_image_urls.append(image_url)
        elif closing_link_bracket and title_text in image_urls:
            new_image_url = image_urls[title_text]
            updated_text = full_match.replace(image_url, new_image_url)
            processed_image_urls.append(image_url)

        text = text.replace(full_match, updated_text)

    if generated_content_present:
        text = f"{text}\n\n{GENERATED_CONTENT_APPENDIX}"
    return text


def parse_images(text: str) -> list[dict]:
    """
    Parse image from markdown text
    The minimum pattern to trigger detection is "![image_name](".
    This pattern usually occurred during text streaming, text will be removed.

    >>> parse_images("Single image text.\\n\\n![image1](image_url1)")
    [{'name': 'image1', 'url': 'image_url1'}]
    >>> parse_images("Text without image")
    []
    >>> parse_images("Image with incomplete url is removed. \\n\\n![image1](im")
    [{'name': 'image1', 'url': 'im'}]
    """
    images = []
    for _, image_name, image_url in parse_image_link(text):
        images.append({"name": image_name, "url": image_url})
    return images


@functools.lru_cache
def get_urls(text: str) -> list[str]:
    """Get link and image urls in text"""
    urls = []
    for matchobj in LINK_MD_PATTERN.finditer(text):
        link_url = matchobj.group("url")
        urls.append(link_url)

    for _, _, image_url in parse_image_link(text):
        urls.append(image_url)
    return urls


def detect_proxy_urls(text: str) -> list[str]:
    """
    >>> detect_proxy_urls("Graph below.\\n![Plot](https://storage.googleapis.com/kagi/graph.png)")
    ['https://storage.googleapis.com/kagi/graph.png']
    """
    urls_to_be_proxied = []
    urls = get_urls(text)
    urls_to_be_proxied = [url for url in urls if is_url_to_be_proxied(url)]
    return urls_to_be_proxied


def normalize_codeblocks(text: str) -> str:
    """
    Dedent codeblocks. This also handles cases where opening and closing fences are indented on different levels, as opposed to simply using `textwrap.dedent() on entire block.`
    """
    output = []
    buffer = []
    in_block = False

    for line in text.split("\n"):
        stripped = line.lstrip()
        if not in_block and stripped.startswith("```"):
            in_block = True
            buffer.append(stripped)
        elif in_block:
            if stripped == "```":
                in_block = False
                content = textwrap.dedent("\n".join(buffer[1:]))
                output.extend([buffer[0], *content.splitlines(), stripped])
                buffer.clear()
            else:
                buffer.append(line)
        else:
            output.append(line)

    if in_block and buffer:
        output.extend(buffer)

    return "\n".join(output)


def unescape_dollar(text: str) -> str:
    """Unescape dollar for readability in markdown text"""
    return re.sub(ESCAPED_DOLLAR_PATTERN, "$", text)


@protect_codeblock(include_inline_code=True)
@regex_precheck("$", PrecheckMode.ALL)
def cleanup_md_dollar(text: str) -> str:
    return unescape_dollar(text)


@protect_codeblock(include_inline_code=True)
@regex_precheck(("\\", "{", "}"), PrecheckMode.ALL)
def remove_latext_text_mode_macros(text: str) -> str:
    text = re.sub(DOCUMENT_CLASS_PATTERN, "", text)
    text = re.sub(BEGIN_PATTERN, "", text)
    text = re.sub(END_PATTERN, "", text)
    return text


def guard_tag(tag_name: str, response: str) -> str:
    """
    If the tag is not a CoT tag, remove text within guarded tag, including the tag;
    however, if there is nothing after the tag and it's closed, preserve the tag content to avoid empty output.
    Otherwise, put the content in a collapsible details block.

    >>> guard_tag("thoughts", "<thoughts")
    ''
    >>> guard_tag("thoughts", "<thoughts>")
    ''
    >>> guard_tag("thoughts", "<thoughts>let me think")
    ''
    >>> guard_tag("thoughts", "<thoughts>let me think</thoughts>")
    'let me think'
    >>> guard_tag("thoughts", "<thoughts>let me think</thoughts>Response.")
    'Response.'
    >>> guard_tag("think", "No tags here")
    'No tags here'
    >>> guard_tag("think", "<think>\\n\\n</think>Hello how are you?")
    'Hello how are you?'
    >>> guard_tag("think", "<think>\\n\\nLet me analyze this\\n\\n</think>")
    '<details><summary>Thinking</summary>Let me analyze this</details>'
    >>> guard_tag("think", "<think>\\n\\nStep 1: analyze\\n\\n</think>Here is the answer")
    '<details><summary>Thinking</summary>\\n\\nStep 1: analyze\\n\\n</details>\\n\\nHere is the answer'
    >>> guard_tag("think", "<think>\\n\\nStill thinking...")
    '<details><summary>Thinking</summary>Still thinking...</details>'
    >>> guard_tag("think", "<think>Still thinking...")
    '<think>Still thinking...'
    >>> guard_tag("think", "<think>\\n\\nWe can solve this with a single line.\\n\\n```python\\n\\n1 + 1\\n\\n```\\n\\n</think>\\n\\nHere is the updated version:")
    '<details><summary>Thinking</summary>\\n\\nWe can solve this with a single line.\\n\\n```python\\n\\n1 + 1\\n\\n```\\n\\n</details>\\n\\nHere is the updated version:'
    """
    open_tag = f"<{tag_name}>"
    close_tag = f"</{tag_name}>"

    response = response.lstrip()

    if tag_name not in COT_TAGS:
        if (len(response) <= len(open_tag) and response in open_tag) or (
            response.startswith(open_tag) and close_tag not in response
        ):
            return ""
        else:
            # if there is nothing after the tag and it's closed, preserve the tag content to avoid empty output
            tag_content, _, remainder = response.removeprefix(
                open_tag
            ).partition(close_tag)
            return remainder if remainder.strip() else tag_content
    else:
        open_tag = f"{open_tag}\n"
        close_tag = f"\n{close_tag}"

        if not response.startswith(open_tag):
            return response

        reasoning, _, answer = response.removeprefix(open_tag).partition(
            close_tag
        )
        if reasoning.strip():
            # NOTE(Rehan): here we use double lines to ensure <summary> tags are treated as their own paragraph, vs being lumped in with answer/reasoning
            # only doing so if answer exists, since we don't run reasoning through markdown conversion
            reasoning = reasoning.strip()
            if answer.strip():
                answer = f"\n\n{answer.lstrip('\n')}"
                reasoning = f"\n\n{reasoning}\n\n"
            return f"<details><summary>Thinking</summary>{reasoning}</details>{answer}"
        else:
            # NOTE(Yiwei): Empty reasoning block from Qwen 3 even with thinking disabled, return answer as is
            return answer


def has_double_escaped_char(text: str) -> bool:
    # taken from html.escape function
    html_chars = ["&", "<", ">", '"', "'"]
    return any(html.escape(html.escape(char)) in text for char in html_chars)


def remove_think_details_tags(content: str) -> str:
    """Remove everything between (and including) thinking details tags from content"""
    if content.lstrip().startswith("<details>"):
        return (
            re.sub(
                r"^(\s*<details><summary>Thinking</summary>.*?</details>\s*)",
                "",
                content,
                flags=re.DOTALL,
            )
            or "."
        )
    return content


def detail_tag_guardrail(text: str) -> str:
    """Close an open <details> block only if the text actually begins with it.
    This avoids wrapping unrelated content while still fixing missing closers.
    >>> detail_tag_guardrail("<details>No close tag")
    '<details>No close tag</details>'
    >>> detail_tag_guardrail("<details>Both tag exist</details>")
    '<details>Both tag exist</details>'
    >>> detail_tag_guardrail("No tags at all")
    'No tags at all'
    """
    if text.startswith("<details>"):
        return f"<details>{text.removeprefix('<details>').removesuffix('</details>')}</details>"
    else:
        return text
