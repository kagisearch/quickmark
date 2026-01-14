// Generate a slug just like GitHub does for markdown headings. It also ensures slugs are unique in the same way GitHub does it.
// The overall goal of this package is to emulate the way GitHub handles generating markdown heading anchors as close as possible.
// It is based on the [github-slugger](https://github.com/Flet/github-slugger) JavaScript package.

// This project is not a markdown or HTML parser: passing `alpha *bravo* charlie`
// or `alpha <em>bravo</em> charlie` doesn’t work.
// Instead pass the plain text value of the heading: `alpha bravo charlie`.

// ## Usage

// ```rust
// let mut slugger = github_slugger::Slugger::default();

// slugger.slug("foo")
// // returns 'foo'

// slugger.slug("foo")
// // returns 'foo-1'

// slugger.slug("bar")
// // returns 'bar'

// slugger.slug("foo")
// // returns 'foo-2'

// slugger.slug("Привет non-latin 你好")
// // returns 'привет-non-latin-你好'

// slugger.slug("😄 emoji")
// // returns '-emoji'

// slugger.reset()

// slugger.slug("foo")
// // returns 'foo'
// ```

// Check test fixtures for more examples.

// If you need, you can also use the underlying implementation which does not keep
// track of the previously slugged strings:

// ```rust
// github_slugger::slug("foo bar baz")
// // returns 'foo-bar-baz'

// github_slugger::slug("foo bar baz")
// // returns the same slug 'foo-bar-baz' because it does not keep track
// ```

use once_cell::sync::Lazy;
use regex::Regex;
use std::collections::HashSet;

#[derive(Default, Debug)]
pub struct Slugger {
    /// The set of slugs we've seen so far
    slugs: HashSet<String>,
}

// See https://github.com/rust-lang/regex/blob/master/UNICODE.md#rl12-properties
// and https://www.compart.com/en/unicode/category/So
static REMOVE_PAT: &str = r"[\p{Other_Number}\p{Close_Punctuation}\p{Final_Punctuation}\p{Initial_Punctuation}\p{Open_Punctuation}\p{Other_Punctuation}\p{Dash_Punctuation}\p{Symbol}\p{Control}\p{Private_Use}\p{Format}\p{Unassigned}\p{Separator}]";
static REMOVE_RE: Lazy<Regex> = Lazy::new(|| Regex::new(REMOVE_PAT).unwrap());

impl Slugger {
    /// Generate a slug for the given string.
    pub fn slug(&mut self, s: &str) -> String {
        // if we've already seen this slug, add a number to the end
        let base = slug(s);
        let mut result = base.clone();
        let mut i = 1;
        while self.slugs.contains(&result) {
            result = format!("{}-{}", base, i);
            i += 1;
        }

        self.slugs.insert(result.clone());
        result
    }

    /// Clear the set of slugs we've seen so far.
    pub fn reset(&mut self) {
        self.slugs.clear();
    }
}

pub fn slug(input: &str) -> String {
    let s = input.to_lowercase();

    // apply function to regex matches
    let s = REMOVE_RE.replace_all(&s, |caps: &regex::Captures| {
        let c = caps.get(0).unwrap().as_str();
        if c == " " || c == "-" {
            "-".to_string()
        } else if c.chars().all(|a| a.is_alphabetic()) {
            // note in "Other Symbols" this matches:
            // ⓐⓑⓒⓓⓔⓕⓖⓗⓘⓙⓚⓛⓜⓝⓞⓟⓠⓡⓢⓣⓤⓥⓦⓧⓨⓩ
            // ⓐⓑⓒⓓⓔⓕⓖⓗⓘⓙⓚⓛⓜⓝⓞⓟⓠⓡⓢⓣⓤⓥⓦⓧⓨⓩ
            // 🄰🄱🄲🄳🄴🄵🄶🄷🄸🄹🄺🄻🄼🄽🄾🄿🅀🅁🅂🅃🅄🅅🅆🅇🅈🅉
            // 🅐🅑🅒🅓🅔🅕🅖🅗🅘🅙🅚🅛🅜🅝🅞🅟🅠🅡🅢🅣🅤🅥🅦🅧🅨🅩
            // 🅰🅱🅲🅳🅴🅵🅶🅷🅸🅹🅺🅻🅼🅽🅾🅿🆀🆁🆂🆃🆄🆅🆆🆇🆈🆉
            c.to_string()
        } else {
            "".to_string()
        }
    });
    s.replace(|c: char| c.is_whitespace(), "-")
}
