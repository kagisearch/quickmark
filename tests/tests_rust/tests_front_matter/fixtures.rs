use std::path::PathBuf;
use testing::fixture;

#[fixture("tests/fixtures/*.md")]
fn test_fixtures(file: PathBuf) {
    let f = dev::read_fixture_file(file);

    let parser = &mut crate::MarkdownIt::new();
    crate::plugins::cmark::add(parser);
    front_matter::add(parser);
    let actual = parser.parse(&f.input).render();

    dev::assert_no_diff(f, &actual);
}
