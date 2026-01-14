use std::path::PathBuf;
use testing::fixture;

#[fixture("tests/fixtures/[!_]*.md")]
fn test_html(file: PathBuf) {
    let f = dev::read_fixture_file(file);

    let parser = &mut crate::MarkdownIt::new();
    crate::plugins::sourcepos::add(parser);
    crate::plugins::cmark::add(parser);
    footnote::add(parser);
    let actual = parser.parse(&f.input).render();

    dev::assert_no_diff(f, &actual);
}
