use crate::mdparser::constants::{MAIL_PREFIX, PHONE_PREFIX};
use fancy_regex::Regex as FancyRegex;
use once_cell::sync::Lazy;
use regex::Regex;
use std::borrow::Cow;

// NOTE(Rehan): using lazy to avoid having the regex recompile every run
// From what I can tell, without lazy, this recompiles every time it is used
// lazy allows it to be compiled at the first run and then keeps it around for subsequent uses
//
// NOTE(Rehan): (from postprocess.py)
// Check if preceded by start of line or whitespace and proceeded by non-word char (e.g punctuation) or end of line
// Do this instead of word boundary, because word boundary includes backslash, which may match within URL
// - Capture group 1 is whitespace prior
// - Capture group 2 is the email
// - Capture group 3 is the whitespace afterwards
pub static EMAIL_REGEX: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"(\s|^)([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})(\W|$)").unwrap()
});

// NOTE(Rehan): (from postprocess.py)
// Currently only support North American phone number format
// - can only be at the start of the text or after an open parenthesis or space (avoid matching in URL)
// - optional country code with +, 1 to 3 digits
// - separator is a must, can be space, hyphen, or period
// - area code in parenthesis or not, 3 digits
// - 3-3-4 format, 10 digits in total
//
// NOTE(Rehan): only diff with this vs the Python version is avoiding the lookback since rust doesn't support
// instead, we actually match the whitespace.
// - Capture group 1 is the whitespace
// - Capture group 2 is the phone number
// - Capture group 3 is the country code
pub static PHONE_NUMBER_REGEX: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"(\s|^|\()((\+?\d{1,3}[\s.-])?(?:\(\d{3}\)|\d{3})[\s.-]\d{3}[\s.-]\d{4})").unwrap()
});

// NOTE(Rehan): port from python
// use FancyRegex crate to use lookbehinds and look ahead, skipped first lookahead through extension logic
// also anchor to beginning of line since we do processing in extension to bring us to opening marker
// ideally we can switch to using regular regex crate instead by working around look behinds/forwards
pub static INLINE_MATH_DOLLAR_REGEX: Lazy<FancyRegex> = Lazy::new(|| {
    FancyRegex::new(
        r"^\$(?P<sp>\s?)(?!\$|\s)(?P<math>[^$\\]*(?:\\.[^$\\]*)*)(?<!\\|\s)(?P=sp)\$(?!\$|[A-Za-z0-9_])",
    )
    .unwrap()
});

// use FancyRegex crate to use lookbehinds and look ahead, skipped first lookahead through extension logic
// also anchor to beginning of line since we do processing in extension to bring us to opening marker
pub static DISPLAY_MATH_DOLLAR_REGEX: Lazy<FancyRegex> =
    Lazy::new(|| FancyRegex::new(r"(?s)^\$\$(?:\n)?(?P<math>.*?)(?<!\\)(?:\n)?\$\$").unwrap());

// mirror INLINE_MATH_PAREN_PATTERN from postprocess.py
// match `\(math\)`, where the opening/closing backslashes are not themselves escaped
pub static INLINE_MATH_PAREN_REGEX: Lazy<FancyRegex> =
    Lazy::new(|| FancyRegex::new(r"^\\\((?P<math>.*?)(?<!\\)\\\)").unwrap());

// mirror DISPLAY_MATH_BRACKET_PATTERN from postprocess.py
// display math can span multiple lines, so enable dotall mode
pub static DISPLAY_MATH_BRACKET_REGEX: Lazy<FancyRegex> =
    Lazy::new(|| FancyRegex::new(r"(?s)^\\\[(?P<math>.*?)(?<!\\)\\\]").unwrap());

pub static CITATION_REGEX: Lazy<Regex> = Lazy::new(|| Regex::new(r"【\d+】").unwrap());

// mirror SINGLE_BACKTICK_PATTERN from postprocess.py
// - no preceding backslash or backtick
// - opening single backtick, not followed by another backtick
// - Capture group "code" is the inline code contents
// - closing single backtick, not followed by another backtick
pub static SINGLE_BACKTICK_REGEX: Lazy<FancyRegex> =
    Lazy::new(|| FancyRegex::new(r"(?<![\\`])`(?P<code>(?:[^\\`]|\\.)+?)`(?!`)").unwrap());

const SINGLE_BACKTICK_PLACEHOLDER: &str = "【‡SINGLE_BACKTICK‡】";

struct Preprocessor {
    name: &'static str,
    processor: fn(Cow<'_, str>) -> Cow<'_, str>,
    include_inline_code: bool,
}

fn apply_regex<'a>(src: Cow<'a, str>, regex: &Regex, replacement: &str) -> Cow<'a, str> {
    // NOTE(Rehan): Cow can be a borrowed value or an owned value
    // the output of regex.replace_all() is a Cow value - borrowed if regex doesn't match, owned if it does and get replaced
    // so made this helper function to be able to input the output of a replace_all, keeping it borrowed if no match/change
    // to avoid making pointless copies of the string
    match src {
        Cow::Borrowed(s) => regex.replace_all(s, replacement),
        Cow::Owned(s) => {
            let result = regex.replace_all(&s, replacement);
            Cow::Owned(result.into_owned())
        }
    }
}

fn apply_contact_info_regex(src: Cow<'_, str>) -> Cow<'_, str> {
    // NOTE(Rehan): this makes phone numbers like <tel:999-999-99999> and emails like <mailto:joedoe@example.com>
    let mut processed = apply_regex(src, &EMAIL_REGEX, &format!("$1<{}$2>$3", MAIL_PREFIX));
    processed = apply_regex(
        processed,
        &PHONE_NUMBER_REGEX,
        &format!("$1<{}$2>", PHONE_PREFIX),
    );
    processed
}

fn replace_single_backticks(src: Cow<'_, str>) -> Cow<'_, str> {
    let result = SINGLE_BACKTICK_REGEX.replace_all(src.as_ref(), |caps: &fancy_regex::Captures| {
        let code = caps.name("code").unwrap().as_str();
        format!("```{SINGLE_BACKTICK_PLACEHOLDER}{code}{SINGLE_BACKTICK_PLACEHOLDER}```")
    });
    Cow::Owned(result.into_owned())
}

fn restore_single_backticks(src: Cow<'_, str>) -> Cow<'_, str> {
    Cow::Owned(
        src.replace(&format!("```{SINGLE_BACKTICK_PLACEHOLDER}"), "`")
            .replace(&format!("{SINGLE_BACKTICK_PLACEHOLDER}```"), "`"),
    )
}

// # NOTE(Rehan): copy Python protect_codeblock flow
// protect valid single-backtick inline spans, split by triple-backtick blocks,
// process only non-code segments, then restore inline code spans.
fn protect_codeblocks(
    src: Cow<'_, str>,
    include_inline_code: bool,
    processor: fn(Cow<'_, str>) -> Cow<'_, str>,
) -> Cow<'_, str> {
    let protected = if include_inline_code {
        replace_single_backticks(src)
    } else {
        src
    };

    let parts: Vec<&str> = protected.split("```").collect();
    let mut result = String::with_capacity(protected.len());

    for (i, part) in parts.iter().enumerate() {
        if i > 0 {
            result.push_str("```");
        }
        if i % 2 == 0 {
            let processed = processor(Cow::Borrowed(part));
            result.push_str(&processed);
        } else {
            result.push_str(part);
        }
    }

    let output = Cow::Owned(result);
    if include_inline_code {
        restore_single_backticks(output)
    } else {
        output
    }
}

fn reenumerate_citations(src: Cow<'_, str>) -> Cow<'_, str> {
    let mut counter = 0;
    let result = CITATION_REGEX.replace_all(&src, |_caps: &regex::Captures| {
        let result = format!("【{}】", counter);
        counter += 1;
        result
    });
    Cow::Owned(result.into_owned())
}

pub fn preprocess<'a>(src: &'a str, enabled_plugins: &[String]) -> Cow<'a, str> {
    let mut processed = Cow::Borrowed(src);

    // NOTE(Rehan): here we can define a preprocessor for each plugin
    // so we only run certain preprocessing if the plugin is enabled
    let processors = vec![
        Preprocessor {
            name: "kagi_contact_info",
            processor: apply_contact_info_regex,
            include_inline_code: true,
        },
        Preprocessor {
            name: "citation",
            processor: reenumerate_citations,
            include_inline_code: true,
        },
    ];

    // NOTE(Rehan): conflicting pattern matches go in order of enabled plugins
    // ideally no conflict though
    for preprocessor in processors {
        if enabled_plugins.contains(&preprocessor.name.to_string()) {
            processed = protect_codeblocks(
                processed,
                preprocessor.include_inline_code,
                preprocessor.processor,
            );
        }
    }

    processed
}
